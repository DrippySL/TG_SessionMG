import asyncio
import random
import logging
import time
from datetime import datetime
from celery import shared_task, current_task
from django.utils.timezone import now
from django.db import transaction
from asgiref.sync import sync_to_async, async_to_sync

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    AuthKeyInvalidError,
    FloodWaitError,
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError
)

from .models import TelegramAccount, TaskQueue, AccountAuditLog, ProxyServer
from .services.session_manager import SessionManager, ThreadLocalDBConnection
from .services.encryption import EncryptionService
from .services.telegram_actions import check_security_alerts
from django.conf import settings

logger = logging.getLogger(__name__)


def get_client_for_account(account_data, account):
    """Создает TelegramClient для аккаунта"""
    import platform
    
    session_data = account_data['session_data']
    if isinstance(session_data, memoryview):
        session_data = session_data.tobytes()
    session_string = session_data.decode('utf-8')
    
    # Получаем параметры устройства
    device_params = account.device_params or {}
    
    # Подготовка параметров прокси, если есть
    proxy_config = None
    if account.proxy:
        if account.proxy.proxy_type == 'mtproto':
            from telethon.network import ConnectionTcpMTProxyRandomizedIntermediate
            proxy_config = (account.proxy.host, account.proxy.port, account.proxy.password)
        else:
            proxy_config = (
                account.proxy.proxy_type,
                account.proxy.host,
                account.proxy.port,
                account.proxy.username,
                account.proxy.password
            )
    
    client = TelegramClient(
        StringSession(session_string),
        account_data['api_id'],
        account_data['api_hash'],
        device_model=device_params.get('device_model', f'CorporateManager_{platform.system()}'),
        system_version=device_params.get('system_version', platform.version()),
        app_version=device_params.get('app_version', '1.0'),
        lang_code=device_params.get('lang_code', 'ru'),
        system_lang_code=device_params.get('system_lang_code', 'ru'),
        proxy=proxy_config
    )
    
    return client


@shared_task(bind=True, name='accounts.tasks.check_account_task', max_retries=3)
def check_account_task(self, account_id, task_queue_id=None):
    """Задача проверки одного аккаунта"""
    logger.info(f"Starting check for account {account_id}, task {self.request.id}")
    
    try:
        # Получаем аккаунт
        account = TelegramAccount.objects.using('telegram_db').get(id=account_id)
        
        # Обновляем статус задачи если есть task_queue_id
        if task_queue_id:
            task = TaskQueue.objects.get(id=task_queue_id)
            task.status = 'processing'
            task.started_at = now()
            task.save()
        
        # Загружаем данные сессии
        session_manager = SessionManager()
        account_data = session_manager.load_account_session(account.phone_number)
        
        if not account_data['session_data']:
            account.activity_status = 'dead'
            account.last_ping = now()
            account.save()
            
            if task_queue_id:
                task.status = 'failed'
                task.error_message = 'Сессия не найдена'
                task.completed_at = now()
                task.save()
            
            return {'status': 'error', 'message': 'Сессия не найдена'}
        
        # Anti-flood задержка
        delay = random.uniform(
            float(settings.TELEGRAM_ANTI_FLOOD_DELAY_MIN),
            float(settings.TELEGRAM_ANTI_FLOOD_DELAY_MAX)
        )
        logger.info(f"Anti-flood delay: {delay:.2f} seconds before checking account {account.phone_number}")
        time.sleep(delay)
        
        # Проверяем аккаунт
        result = async_to_sync(check_account_async)(account, account_data)
        
        # Обновляем задачу если есть task_queue_id
        if task_queue_id:
            task.status = 'completed'
            task.result = result
            task.completed_at = now()
            task.save()
        
        return result
        
    except Exception as e:
        logger.error(f"Error checking account {account_id}: {e}", exc_info=True)
        
        if task_queue_id:
            task = TaskQueue.objects.get(id=task_queue_id)
            task.status = 'failed'
            task.error_message = str(e)
            task.completed_at = now()
            task.save()
        
        self.retry(exc=e, countdown=60)
        
    finally:
        ThreadLocalDBConnection.close_all()


async def check_account_async(account, account_data):
    """Асинхронная проверка аккаунта"""
    client = None
    try:
        client = get_client_for_account(account_data, account)
        await client.connect()
        
        # Проверяем авторизацию
        if not await client.is_user_authorized():
            # Проверяем, не была ли сессия Менеджера завершена извне
            last_check = account.last_checked
            current_time = now()
            
            if last_check:
                time_since_last_check = current_time - last_check
                # Если прошло меньше 1 часа с последней проверки, скорее всего сессия была завершена принудительно
                if time_since_last_check.total_seconds() < 3600:
                    alert_type = 'recent'
                else:
                    # Если прошло больше часа, но сессия все равно не работает - тоже алерт
                    alert_type = 'old'
            else:
                # Если не было предыдущих проверок, но аккаунт не авторизован - подозрительно
                alert_type = 'first_check'
            
            # Создаем алерт в любом случае, если аккаунт не авторизован
            if alert_type:
                    current_device_params = account.device_params or {}
                    current_security_info = current_device_params.get('security_info', {})
                    alert_history = current_security_info.get('alert_history', [])
                    
                    if alert_type == 'recent':
                        message = f'⚠️ СЕССИЯ МЕНЕДЖЕРА ЗАВЕРШЕНА: Обнаружено при проверке в {current_time.strftime("%H:%M:%S %d.%m.%Y")} (недавнее событие)'
                    elif alert_type == 'old':
                        message = f'⚠️ СЕССИЯ МЕНЕДЖЕРА НЕАКТИВНА: Обнаружено при проверке в {current_time.strftime("%H:%M:%S %d.%m.%Y")} (давнее событие)'
                    else:  # first_check
                        message = f'⚠️ СЕССИЯ МЕНЕДЖЕРА ЗАВЕРШЕНА: Обнаружено при первой проверке в {current_time.strftime("%H:%M:%S %d.%m.%Y")}'
                    
                    manager_terminated_alert = {
                        'message': message,
                        'detected_at': current_time.isoformat(),
                        'acknowledged': False,
                        'context': f'manager_session_lost_{alert_type}',
                        'severity': 'high'
                    }
                    alert_history.insert(0, manager_terminated_alert)
                    alert_history = alert_history[:10]
                    
                    current_device_params['security_info'] = {
                        'has_security_alert': True,
                        'alert_message': manager_terminated_alert['message'],
                        'last_security_check': current_time.isoformat(),
                        'alert_history': alert_history
                    }
                    account.device_params = current_device_params
                    logger.warning(f"Manager session lost detected for {account.phone_number}")
            
            account.activity_status = 'dead'
            account.last_ping = current_time
            account.last_checked = current_time
            await sync_to_async(account.save)()
            
            await sync_to_async(AccountAuditLog.objects.using('telegram_db').create)(
                account=account,
                action_type='check_failed',
                action_details={'reason': 'not_authorized'},
                performed_by='Система'
            )
            
            return {'status': 'error', 'message': 'Не авторизован'}
        
        # Проверяем безопасность (сообщения от сервисного канала)
        has_security_alert, alert_message = await check_security_alerts(client, account.phone_number)
        
        # Имитируем активность - получаем диалоги
        try:
            dialogs = await client.get_dialogs(limit=settings.TELEGRAM_GET_DIALOGS_LIMIT)
            dialog_count = len(dialogs) if dialogs else 0
            logger.info(f"Got {dialog_count} dialogs for {account.phone_number}")
        except Exception as e:
            logger.warning(f"Could not get dialogs for {account.phone_number}: {e}")
            dialog_count = 0
        
        # Сохраняем информацию о безопасности с историей
        current_device_params = account.device_params or {}
        current_security_info = current_device_params.get('security_info', {})
        alert_history = current_security_info.get('alert_history', [])
        
        # Если есть новый алерт от Telegram, сохраняем его в историю
        if has_security_alert and alert_message:
            new_alert = {
                'message': alert_message,
                'detected_at': now().isoformat(),
                'acknowledged': False,
                'context': 'telegram_security'
            }
            # Добавляем новый алерт в начало истории (максимум 10 последних)
            alert_history.insert(0, new_alert)
            alert_history = alert_history[:10]  # Ограничиваем историю
        
        
        # Обновляем статус аккаунта (после проверки безопасности)
        account.last_ping = current_time
        account.activity_status = 'active'  # Будет перезаписано в 'dead' если авторизация не прошла
        account.last_checked = current_time
        
        security_info = {
            'has_security_alert': has_security_alert or len(alert_history) > 0,
            'alert_message': alert_message if has_security_alert else (alert_history[0]['message'] if alert_history else ''),
            'last_security_check': current_time.isoformat(),
            'alert_history': alert_history
        }
        
        # Обновляем device_params с информацией о безопасности
        current_device_params['security_info'] = security_info
        account.device_params = current_device_params
        
        await sync_to_async(account.save)()
        
        # Логируем успешную проверку
        audit_details = {
            'dialog_count': dialog_count,
            'has_security_alert': has_security_alert,
            'alert_message': alert_message
        }
        
        await sync_to_async(AccountAuditLog.objects.using('telegram_db').create)(
            account=account,
            action_type='check_success',
            action_details=audit_details,
            performed_by='Система'
        )
        
        return {
            'status': 'success',
            'message': 'Аккаунт активен',
            'dialog_count': dialog_count,
            'last_ping': account.last_ping.isoformat(),
            'has_security_alert': has_security_alert,
            'alert_message': alert_message
        }
        
    except AuthKeyInvalidError as e:
        logger.error(f"AuthKeyInvalidError for {account.phone_number}: {e}")
        
        account.activity_status = 'dead'
        account.last_ping = now()
        await sync_to_async(account.save)()
        
        await sync_to_async(AccountAuditLog.objects.using('telegram_db').create)(
            account=account,
            action_type='session_invalid',
            action_details={'error': str(e)},
            performed_by='Система'
        )
        
        return {'status': 'error', 'message': 'Ключ авторизации невалиден'}
        
    except FloodWaitError as e:
        logger.error(f"FloodWaitError for {account.phone_number}: wait {e.seconds} seconds")
        
        account.activity_status = 'flood'
        account.last_ping = now()
        await sync_to_async(account.save)()
        
        # Создаем задачу на паузу
        from celery.exceptions import Ignore
        check_account_task.apply_async(
            args=[account.id],
            countdown=e.seconds + 10
        )
        
        await sync_to_async(AccountAuditLog.objects.using('telegram_db').create)(
            account=account,
            action_type='flood_wait',
            action_details={'wait_seconds': e.seconds},
            performed_by='Система'
        )
        
        raise Ignore()
        
    except Exception as e:
        logger.error(f"Error checking account {account.phone_number}: {e}", exc_info=True)
        
        account.activity_status = 'dead'
        account.last_ping = now()
        await sync_to_async(account.save)()
        
        return {'status': 'error', 'message': str(e)}
        
    finally:
        if client:
            await client.disconnect()


@shared_task(bind=True, name='accounts.tasks.bulk_check_accounts_task')
def bulk_check_accounts_task(self, account_ids, task_queue_id):
    """Задача групповой проверки аккаунтов"""
    logger.info(f"Starting bulk check for {len(account_ids)} accounts")
    
    try:
        task = TaskQueue.objects.get(id=task_queue_id)
        task.status = 'processing'
        task.started_at = now()
        task.save()
        
        total = len(account_ids)
        completed = 0
        results = []
        
        for i, account_id in enumerate(account_ids):
            # Обновляем прогресс
            progress = int((i / total) * 100)
            task.progress = progress
            task.save()
            
            # Выполняем проверку аккаунта
            try:
                result = check_account_task(account_id)
                results.append({
                    'account_id': account_id,
                    'result': result
                })
                completed += 1
                
            except Exception as e:
                logger.error(f"Error checking account {account_id}: {e}")
                results.append({
                    'account_id': account_id,
                    'error': str(e)
                })
            
            # Anti-flood задержка между аккаунтами (60-120 секунд)
            if i < total - 1:  # Не ждать после последнего аккаунта
                delay = random.uniform(60, 120)
                logger.info(f"Anti-flood delay between accounts: {delay:.2f} seconds")
                time.sleep(delay)
        
        # Завершаем задачу
        task.status = 'completed'
        task.progress = 100
        task.result = {
            'total': total,
            'completed': completed,
            'results': results
        }
        task.completed_at = now()
        task.save()
        
        return task.result
        
    except Exception as e:
        logger.error(f"Error in bulk check task: {e}", exc_info=True)
        
        if 'task' in locals():
            task.status = 'failed'
            task.error_message = str(e)
            task.completed_at = now()
            task.save()
        
        raise


@shared_task(bind=True, name='accounts.tasks.reauthorize_account_task')
def reauthorize_account_task(self, account_id, task_queue_id=None):
    """Задача повторной авторизации аккаунта"""
    logger.info(f"Starting reauthorization for account {account_id}")
    
    try:
        from .services.telegram_actions import reauthorize_account, verify_reauthorization
        
        account = TelegramAccount.objects.using('telegram_db').get(id=account_id)
        
        if task_queue_id:
            task = TaskQueue.objects.get(id=task_queue_id)
            task.status = 'processing'
            task.started_at = now()
            task.save()
        
        # Первый шаг - отправка кода
        result = async_to_sync(reauthorize_account)(account_id)
        
        if 'error' in result:
            if task_queue_id:
                task.status = 'failed'
                task.error_message = result['error']
                task.completed_at = now()
                task.save()
            return result
        
        # Задача ожидает ввода кода пользователем
        # Фактическая проверка кода будет выполнена через verify_reauthorization
        
        if task_queue_id:
            task.status = 'completed'
            task.result = result
            task.completed_at = now()
            task.save()
        
        return result
        
    except Exception as e:
        logger.error(f"Error in reauthorization task: {e}", exc_info=True)
        
        if task_queue_id:
            task.status = 'failed'
            task.error_message = str(e)
            task.completed_at = now()
            task.save()
        
        return {'error': str(e)}


@shared_task(bind=True, name='accounts.tasks.reclaim_account_task')
def reclaim_account_task(self, account_id, two_factor_password=None, task_queue_id=None):
    """Задача возврата аккаунта"""
    logger.info(f"Starting reclaim task for account {account_id}")
    
    try:
        from .services.telegram_actions import reclaim_account
        
        if task_queue_id:
            task = TaskQueue.objects.get(id=task_queue_id)
            task.status = 'processing'
            task.started_at = now()
            task.save()
        
        result = async_to_sync(reclaim_account)(account_id, two_factor_password)
        
        if task_queue_id:
            if 'error' in result:
                task.status = 'failed'
                task.error_message = result.get('error', 'Unknown error')
            else:
                task.status = 'completed'
                task.result = result
            task.completed_at = now()
            task.save()
        
        return result
        
    except Exception as e:
        logger.error(f"Error in reclaim task: {e}", exc_info=True)
        
        if task_queue_id:
            task.status = 'failed'
            task.error_message = str(e)
            task.completed_at = now()
            task.save()
        
        return {'error': str(e)}
    
    finally:
        ThreadLocalDBConnection.close_all()


@shared_task(name='accounts.tasks.cleanup_old_tasks')
def cleanup_old_tasks():
    """Очистка старых задач из очереди"""
    from django.utils.timezone import now, timedelta
    
    week_ago = now() - timedelta(days=7)
    deleted_count, _ = TaskQueue.objects.filter(
        created_at__lt=week_ago,
        status__in=['completed', 'failed', 'cancelled']
    ).delete()
    
    logger.info(f"Cleaned up {deleted_count} old tasks")
    return deleted_count


@shared_task(name='accounts.tasks.daily_check_all_active_accounts')
def daily_check_all_active_accounts():
    """Ежедневная проверка всех активных аккаунтов"""
    from .models import TelegramAccount, TaskQueue
    
    active_accounts = TelegramAccount.objects.using('telegram_db').filter(
        account_status='active'
    ).values_list('id', flat=True)
    
    account_ids = list(active_accounts)
    
    if not account_ids:
        logger.info("No active accounts found for daily check")
        return
    
    # Создаем запись в очереди задач
    task = TaskQueue.objects.create(
        task_type='bulk_check',
        account_ids=account_ids,
        parameters={'scheduled': True, 'daily_check': True},
        created_by='Система'
    )
    
    # Запускаем задачу Celery
    bulk_check_accounts_task.delay(account_ids, task.id)
    
    logger.info(f"Scheduled daily check for {len(account_ids)} accounts, task ID: {task.id}")
    return f"Scheduled daily check for {len(account_ids)} accounts, task ID: {task.id}"
