import asyncio
import logging
import json
import sys
import platform
import time
import datetime
from datetime import timezone
from telethon import TelegramClient, version
from telethon.sessions import StringSession
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    PasswordHashInvalidError,
    PhoneNumberUnoccupiedError,
    PhoneNumberFloodError,
    FloodWaitError,
    ApiIdInvalidError
)
from telethon.tl.functions.auth import ResetAuthorizationsRequest
from telethon.tl.functions.account import GetAuthorizationsRequest, ResetAuthorizationRequest, SendChangePhoneCodeRequest
from asgiref.sync import sync_to_async, async_to_sync
from .session_manager import SessionManager, ThreadLocalDBConnection
from .encryption import EncryptionService
from ..models import TelegramAccount, AccountAuditLog, GlobalAppSettings, ProxyServer
import random
import string

logger = logging.getLogger(__name__)


async def check_security_alerts(client, phone):
    """
    Проверяет последние сообщения от сервисного канала Telegram (ID 777000)
    на наличие сигналов о попытках изменения безопасности аккаунта.
    """
    try:
        # Ищем сообщения от официального канала Telegram (ID 777000)
        async for message in client.iter_messages(777000, limit=20):
            text = message.text.lower() if message.text else ''
            triggers = ['password', 'recovery', 'email', 'пароль', 'почта', 'сброс', 'код', 'code', 'reset', 'изменение', 'change', 'login', 'вход', 'device', 'устройство']

            # Если сообщение свежее (за последние 48 часов) и содержит триггер
            message_time = message.date
            current_time = datetime.datetime.now(timezone.utc)
            time_diff = current_time - message_time

            if time_diff.total_seconds() < 172800:  # 48 часов (увеличили для надежности)
                if any(word in text for word in triggers):
                    logger.info(f"Security alert found for {phone}: {message.text[:100]}...")
                    # НЕ помечаем как прочитанное! Позволяем пользователю видеть алерт
                    return True, message.text

        return False, None

    except Exception as e:
        logger.error(f"Error checking security alerts for {phone}: {e}")
        return False, None


def change_password(account_id, old_password=None, new_password=None):
    """Change password for Telegram account"""
    try:
        return async_to_sync(_change_password_async)(account_id, old_password, new_password)
    except Exception as e:
        logger.error(f"Error in change_password: {e}")
        raise
    finally:
        ThreadLocalDBConnection.close_all()


async def _change_password_async(account_id, old_password=None, new_password=None):
    try:
        account = await sync_to_async(TelegramAccount.objects.using('telegram_db').get)(id=account_id)

        session_manager = SessionManager()
        account_data = await sync_to_async(session_manager.load_account_session)(account.phone_number)

        if account_data['account_status'] != 'active':
            return "Аккаунт не активен"

        if not account_data['session_data']:
            return "Данные сессии не найдены"

        session_data = account_data['session_data']
        if isinstance(session_data, memoryview):
            session_data = session_data.tobytes()
        session_string = session_data.decode('utf-8')

        # Получаем параметры устройства и прокси
        device_params = account.device_params or {}
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

        await client.connect()

        if not await client.is_user_authorized():
            await client.disconnect()
            return "Не авторизован"

        try:
            me = await client.get_me()

            try:
                await client.edit_2fa(
                    current_password=old_password if old_password else '',
                    new_password=new_password
                )
                password_changed = True
            except PasswordHashInvalidError:
                try:
                    await client.edit_2fa(
                        current_password='',
                        new_password=new_password
                    )
                    password_changed = True
                except Exception as e:
                    logger.error(f"Ошибка при установке пароля без 2FA: {e}")
                    return f"Не удалось установить пароль. Возможно, 2FA уже включено и требуется старый пароль."
            except SessionPasswordNeededError:
                return "Требуется пароль 2FA. Пожалуйста, предоставьте старый пароль."
            except Exception as e:
                logger.error(f"Ошибка при изменении пароля: {e}")
                return f"Не удалось изменить пароль: {str(e)}"

            if password_changed:
                await sync_to_async(AccountAuditLog.objects.using('telegram_db').create)(
                    account=account,
                    action_type="password_changed",
                    action_details={"password_changed": True, "has_2fa": old_password is not None},
                    performed_by="Система"
                )

                return f"Пароль успешно изменен для {account.phone_number}. Новый пароль: {new_password}"
            else:
                return "Не удалось изменить пароль"

        finally:
            await client.disconnect()

    except Exception as e:
        logger.error(f"Ошибка при смене пароля: {e}")
        return f"Ошибка: {str(e)}"


def send_code(phone, employee_id, employee_fio, account_note, recovery_email):
    """Send verification code for new account"""
    try:
        return async_to_sync(_send_code_async)(phone, employee_id, employee_fio, account_note, recovery_email)
    except Exception as e:
        logger.error(f"Error in send_code: {e}")
        raise
    finally:
        ThreadLocalDBConnection.close_all()


async def _send_code_async(phone, employee_id, employee_fio, account_note, recovery_email):
    try:
        logger.info(f"Starting send_code for {phone}")
        logger.info(f"Telethon version: {version.__version__}")

        if not all([phone, employee_id, employee_fio, recovery_email]):
            return {"error": "Все поля обязательны для заполнения"}

        session_manager = SessionManager()
        settings = await sync_to_async(GlobalAppSettings.objects.using('telegram_db').filter(is_active=True).first)()
        if not settings:
            return {"error": "Глобальные настройки приложения не настроены"}

        api_id, api_hash = settings.api_id, settings.api_hash
        logger.info(f"Using API ID: {api_id}, API Hash: {api_hash[:10]}...")

        client = TelegramClient(
            StringSession(),
            api_id,
            api_hash,
            device_model=f"CorporateManager_{platform.system()}",
            system_version=platform.version(),
            app_version="1.0",
            lang_code="ru",
            system_lang_code="ru"
        )

        await client.connect()
        logger.info(f"Connected to Telegram, connection status: {client.is_connected()}")

        try:
            logger.info(f"Sending code request to {phone}")
            result = await client.send_code_request(
                phone,
                force_sms=True
            )
            phone_code_hash = result.phone_code_hash
            logger.info(f"Phone code hash received: {phone_code_hash[:20]}...")

            session_string = client.session.save()
            session_data = session_string.encode('utf-8')

            await client.disconnect()

            success = await sync_to_async(session_manager.save_account_session)(
                phone_number=phone,
                session_data=session_data,
                recovery_email=recovery_email,
                employee_id=employee_id,
                employee_fio=employee_fio,
                account_note=account_note,
                account_status='pending',
                phone_code_hash=phone_code_hash
            )

            if success:
                logger.info(f"Successfully saved session for {phone}")
                return {"message": f"Код подтверждения отправлен на {phone}. Пожалуйста, проверьте SMS сообщение."}
            else:
                return {"error": f"Код отправлен, но не удалось сохранить данные аккаунта"}

        except ApiIdInvalidError as e:
            await client.disconnect()
            logger.error(f"Invalid API ID/API Hash: {e}")
            return {"error": "Ошибка API Telegram. Проверьте API ID и API Hash в глобальных настройках."}
        except PhoneNumberFloodError as e:
            await client.disconnect()
            logger.error(f"Phone number flood error: {e}")
            return {"error": f"Слишком много запросов для этого номера. Пожалуйста, попробуйте позже через {e.seconds} секунд."}
        except FloodWaitError as e:
            await client.disconnect()
            logger.error(f"Flood wait error: {e}")
            return {"error": f"Слишком много запросов. Пожалуйста, попробуйте позже через {e.seconds} секунд."}
        except Exception as e:
            await client.disconnect()
            logger.error(f"Ошибка отправки кода: {type(e).__name__}: {e}", exc_info=True)
            return {"error": f"Ошибка отправки кода: {str(e)}"}

    except Exception as e:
        logger.error(f"Общая ошибка отправки кода: {type(e).__name__}: {e}", exc_info=True)
        return {"error": f"Ошибка: {str(e)}"}


def verify_code(phone, code, employee_id, employee_fio, account_note, recovery_email, two_factor_password=None):
    """Verify code and save account"""
    try:
        return async_to_sync(_verify_code_async)(phone, code, employee_id, employee_fio, account_note, recovery_email, two_factor_password)
    except Exception as e:
        logger.error(f"Error in verify_code: {e}")
        raise
    finally:
        ThreadLocalDBConnection.close_all()


async def _verify_code_async(phone, code, employee_id, employee_fio, account_note, recovery_email, two_factor_password=None):
    try:
        logger.info(f"Starting verify_code for {phone}")

        session_manager = SessionManager()
        settings = await sync_to_async(GlobalAppSettings.objects.using('telegram_db').filter(is_active=True).first)()
        if not settings:
            return {"error": "Глобальные настройки приложения не настроены"}

        api_id, api_hash = settings.api_id, settings.api_hash

        account_data = await sync_to_async(session_manager.load_account_session)(phone)
        logger.info(f"Loaded account data for {phone}, status: {account_data.get('account_status')}")

        if not account_data['session_data']:
            return {"error": "Сессия не найдена. Пожалуйста, отправьте код снова."}

        session_data = account_data['session_data']
        if isinstance(session_data, memoryview):
            session_data = session_data.tobytes()
        session_string = session_data.decode('utf-8')

        client = TelegramClient(
            StringSession(session_string),
            api_id,
            api_hash,
            device_model=f"CorporateManager_{platform.system()}",
            system_version=platform.version(),
            app_version="1.0",
            lang_code="ru",
            system_lang_code="ru"
        )
        await client.connect()

        # Если передан пароль 2FA, то пытаемся войти с паролем
        if two_factor_password:
            try:
                await client.sign_in(password=two_factor_password)
                # Успешный вход с паролем
                new_session_string = client.session.save()
                new_session_data = new_session_string.encode('utf-8')

                success = await sync_to_async(session_manager.update_session)(
                    phone_number=phone,
                    new_session_data=new_session_data
                )

                await client.disconnect()

                if success:
                    account = await sync_to_async(TelegramAccount.objects.using('telegram_db').get)(phone_number=phone)
                    account.is_2fa_enabled = True
                    account.account_status = 'active'
                    await sync_to_async(account.save)()

                    await sync_to_async(AccountAuditLog.objects.using('telegram_db').create)(
                        account=account,
                        action_type="account_added",
                        action_details={"employee_id": employee_id, "employee_fio": employee_fio, "2fa_enabled": True},
                        performed_by="Система"
                    )
                    logger.info(f"Account {phone} successfully added and activated with 2FA")
                    return {"message": f"Аккаунт {phone} успешно добавлен и активирован (с поддержкой 2FA)."}
                else:
                    return {"error": f"Не удалось сохранить аккаунт {phone}"}

            except Exception as e:
                await client.disconnect()
                logger.error(f"Ошибка входа с паролем 2FA для {phone}: {type(e).__name__}: {e}", exc_info=True)
                return {"error": f"Неверный пароль 2FA: {str(e)}"}
        else:
            # Вход с кодом подтверждения
            phone_code_hash = account_data.get('phone_code_hash')
            if not phone_code_hash:
                logger.warning(f"No phone_code_hash found for {phone}")
                return {"error": "Код подтверждения не был запрошен или истек. Пожалуйста, отправьте код снова."}

            try:
                logger.info(f"Attempting sign_in for {phone}")
                await client.sign_in(
                    phone=phone,
                    code=code,
                    phone_code_hash=phone_code_hash
                )

            except PhoneCodeInvalidError:
                await client.disconnect()
                logger.warning(f"Invalid phone code for {phone}")
                return {"error": "Неверный код подтверждения"}

            except PhoneCodeExpiredError:
                await client.disconnect()
                logger.warning(f"Phone code expired for {phone}")
                await sync_to_async(session_manager.clear_phone_code_hash)(phone)
                return {"error": "Код подтверждения истек. Пожалуйста, запросите новый код."}

            except SessionPasswordNeededError:
                logger.warning(f"2FA password needed for {phone}")

                # Сохраняем сессию с статусом pending_2fa и phone_code_hash
                session_string = client.session.save()
                session_data = session_string.encode('utf-8')

                await client.disconnect()

                success = await sync_to_async(session_manager.save_account_session)(
                    phone_number=phone,
                    session_data=session_data,
                    recovery_email=recovery_email,
                    employee_id=employee_id,
                    employee_fio=employee_fio,
                    account_note=account_note,
                    account_status='pending_2fa',
                    phone_code_hash=phone_code_hash
                )

                if success:
                    return {"error": "Требуется пароль 2FA", "requires_2fa": True}
                else:
                    return {"error": "Требуется пароль 2FA, но не удалось сохранить состояние сессии"}

            except PhoneNumberUnoccupiedError:
                await client.disconnect()
                logger.warning(f"Phone number {phone} is not registered in Telegram")
                return {"error": "Номер телефона не зарегистрирован в Telegram. Пожалуйста, сначала создайте аккаунт в приложении Telegram."}

            except Exception as e:
                await client.disconnect()
                logger.error(f"Ошибка верификации кода: {type(e).__name__}: {e}", exc_info=True)
                return {"error": f"Ошибка: {str(e)}"}

            # Если код верный и 2FA не требуется
            try:
                new_session_string = client.session.save()
                new_session_data = new_session_string.encode('utf-8')

                success = await sync_to_async(session_manager.update_session)(
                    phone_number=phone,
                    new_session_data=new_session_data
                )

                await client.disconnect()

                if success:
                    account = await sync_to_async(TelegramAccount.objects.using('telegram_db').get)(phone_number=phone)
                    account.account_status = 'active'
                    await sync_to_async(account.save)()

                    await sync_to_async(AccountAuditLog.objects.using('telegram_db').create)(
                        account=account,
                        action_type="account_added",
                        action_details={"employee_id": employee_id, "employee_fio": employee_fio, "2fa_enabled": False},
                        performed_by="Система"
                    )
                    logger.info(f"Account {phone} successfully added and activated")
                    return {"message": f"Аккаунт {phone} успешно добавлен и активирован."}
                else:
                    return {"error": f"Не удалось сохранить аккаунт {phone}"}

            except Exception as e:
                await client.disconnect()
                logger.error(f"Ошибка после успешной авторизации: {e}")
                return {"error": f"Ошибка при сохранении сессии: {str(e)}"}

    except Exception as e:
        logger.error(f"Общая ошибка проверки кода: {type(e).__name__}: {e}", exc_info=True)
        return {"error": f"Ошибка: {str(e)}"}


def delete_session(account_id):
    """Delete session file for account"""
    try:
        return async_to_sync(_delete_session_async)(account_id)
    except Exception as e:
        logger.error(f"Error in delete_session: {e}")
        raise
    finally:
        ThreadLocalDBConnection.close_all()


async def _delete_session_async(account_id):
    try:
        account = await sync_to_async(TelegramAccount.objects.using('telegram_db').get)(id=account_id)
        session_manager = SessionManager()

        success = await sync_to_async(session_manager.delete_session)(account.phone_number)

        if success:
            await sync_to_async(AccountAuditLog.objects.using('telegram_db').create)(
                account=account,
                action_type="session_deleted",
                action_details={"session_cleared": True},
                performed_by="Система"
            )
            return f"Сессия удалена для {account.phone_number}"
        else:
            return f"Не удалось удалить сессию для {account.phone_number}"

    except Exception as e:
        logger.error(f"Ошибка удаления сессии: {e}")
        return f"Ошибка: {str(e)}"


def get_account_details(account_id):
    """Get account details"""
    try:
        return async_to_sync(_get_account_details_async)(account_id)
    except Exception as e:
        logger.error(f"Error in get_account_details: {e}")
        raise
    finally:
        ThreadLocalDBConnection.close_all()


async def _get_account_details_async(account_id):
    try:
        account = await sync_to_async(TelegramAccount.objects.using('telegram_db').get)(id=account_id)
        session_manager = SessionManager()
        account_data = await sync_to_async(session_manager.load_account_session)(account.phone_number)

        details = f"""
        Телефон: {account.phone_number}
        Сотрудник: {account.employee_fio}
        ID сотрудника: {account.employee_id}
        Статус: {account.account_status}
        Статус активности: {account.activity_status}
        2FA: {'Включено' if account_data['is_2fa_enabled'] else 'Отключено'}
        Последняя активность: {account.last_ping}
        Email для восстановления: {account_data['recovery_email']}
        Параметры устройства: {account.device_params}
        Прокси: {account.proxy.name if account.proxy else 'Нет'}
        Последнее обновление: {account.session_updated_at}
        API ID: {account_data['api_id']}
        API Hash: {account_data['api_hash'][:10]}...
        """

        return details
    except Exception as e:
        logger.error(f"Ошибка получения деталей аккаунта: {e}")
        return f"Ошибка: {str(e)}"


def reclaim_account(account_id, two_factor_password=None):
    """Reclaim account procedure - terminate ALL sessions on all devices"""
    try:
        return async_to_sync(_reclaim_account_async)(account_id, two_factor_password)
    except Exception as e:
        logger.error(f"Error in reclaim_account: {e}")
        raise
    finally:
        ThreadLocalDBConnection.close_all()


async def _reclaim_account_async(account_id, two_factor_password=None):
    """
    Reclaim account procedure:
    1. Get all active sessions
    2. Terminate ALL sessions except current one by one
    3. Change password if 2FA is not enabled or we have old password
    4. Log out from current session
    5. Delete session from database
    6. Update account status to 'reclaimed'
    """
    try:
        account = await sync_to_async(TelegramAccount.objects.using('telegram_db').get)(id=account_id)

        logger.info(f"Starting reclaim procedure for account {account.phone_number} (ID: {account_id})")

        session_manager = SessionManager()
        account_data = await sync_to_async(session_manager.load_account_session)(account.phone_number)

        if account_data['account_status'] != 'active':
            return "Аккаунт не активен"

        if not account_data['session_data']:
            return "Данные сессии не найдены"

        session_data = account_data['session_data']
        if isinstance(session_data, memoryview):
            session_data = session_data.tobytes()
        session_string = session_data.decode('utf-8')

        # Получаем параметры устройства и прокси
        device_params = account.device_params or {}
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

        await client.connect()

        if not await client.is_user_authorized():
            await client.disconnect()
            return "Не авторизован"

        try:
            sessions_terminated = False
            
            # Проверяем безопасность перед завершением сессий
            try:
                logger.info(f"Checking security alerts before reclaim for {account.phone_number}")
                has_security_alert, alert_message = await check_security_alerts(client, account.phone_number)
                if has_security_alert:
                    logger.warning(f"SECURITY ALERT during reclaim: {account.phone_number} - {alert_message}")
                    # Сохраняем алерт в device_params
                    current_device_params = account.device_params or {}
                    current_security_info = current_device_params.get('security_info', {})
                    alert_history = current_security_info.get('alert_history', [])
                    
                    new_alert = {
                        'message': alert_message,
                        'detected_at': datetime.datetime.now(timezone.utc).isoformat(),
                        'acknowledged': False,
                        'context': 'account_reclaim'
                    }
                    alert_history.insert(0, new_alert)
                    alert_history = alert_history[:10]
                    
                    current_device_params['security_info'] = {
                        'has_security_alert': True,
                        'alert_message': alert_message,
                        'last_security_check': datetime.datetime.now(timezone.utc).isoformat(),
                        'alert_history': alert_history
                    }
                    account.device_params = current_device_params
                    await sync_to_async(account.save)()
            except Exception as e:
                logger.error(f"Error checking security alerts during reclaim: {e}")

            # 100% надежный метод - завершаем все сессии через ResetAuthorizationsRequest
            try:
                logger.info(f"Resetting all authorizations for {account.phone_number}")
                result = await client(ResetAuthorizationsRequest())
                logger.info(f"Reset all authorizations for {account.phone_number}")
                sessions_terminated = True
            except Exception as e:
                logger.error(f"Failed to reset authorizations: {e}")
                sessions_terminated = False

            # Смена пароля
            new_password = ''.join(random.choices(string.ascii_letters + string.digits + '!@#$%^&*', k=16))
            password_changed = False

            try:
                await client.edit_2fa(
                    current_password=two_factor_password if two_factor_password else '',
                    new_password=new_password
                )
                password_changed = True
                logger.info(f"Password changed for {account.phone_number}")
            except SessionPasswordNeededError:
                logger.warning(f"2FA включено для {account.phone_number}, требуется пароль")
            except Exception as e:
                logger.warning(f"Не удалось сменить пароль для {account.phone_number}: {e}")

            # Выход из текущей сессии
            try:
                await client.log_out()
                logger.info(f"Logged out from current session for {account.phone_number}")
            except Exception as e:
                logger.warning(f"Не удалось выйти из сессии: {e}")

            await client.disconnect()

            # Удаление сессии из базы данных
            success = await sync_to_async(session_manager.delete_session)(account.phone_number)

            if not success:
                logger.warning(f"Failed to delete session from database for {account.phone_number}")

            # Обновление статуса аккаунта
            account.account_status = 'reclaimed'
            account.activity_status = 'dead'
            await sync_to_async(account.save)()

            await sync_to_async(AccountAuditLog.objects.using('telegram_db').create)(
                account=account,
                action_type="account_reclaimed",
                action_details={
                    "password_changed": password_changed,
                    "new_password": new_password if password_changed else None,
                    "sessions_terminated": sessions_terminated,
                    "2fa_used": two_factor_password is not None
                },
                performed_by="Система"
            )

            logger.info(f"Reclaim procedure completed for {account.phone_number}")

            if password_changed and sessions_terminated:
                return f"Аккаунт {account.phone_number} успешно возвращен. Все сессии завершены. Новый пароль: {new_password}"
            elif sessions_terminated:
                return f"Аккаунт {account.phone_number} возвращен. Все сессии завершены. Не удалось сменить пароль (2FA включено или требуется старый пароль)."
            else:
                return f"Аккаунт {account.phone_number} возвращен с ограниченным успехом. Не удалось завершить все сессии."

        except Exception as e:
            await client.disconnect()
            logger.error(f"Ошибка возврата аккаунта: {e}", exc_info=True)
            return f"Ошибка возврата аккаунта: {str(e)}"

    except Exception as e:
        logger.error(f"Ошибка возврата аккаунта: {e}", exc_info=True)
        return f"Ошибка: {str(e)}"


def reauthorize_account(account_id, two_factor_password=None):
    """Reauthorize account - send new verification code and get new session"""
    try:
        return async_to_sync(_reauthorize_account_async)(account_id, two_factor_password)
    except Exception as e:
        logger.error(f"Error in reauthorize_account: {e}")
        raise
    finally:
        ThreadLocalDBConnection.close_all()


async def _reauthorize_account_async(account_id, two_factor_password=None):
    """
    Reauthorize account procedure:
    1. Get account details
    2. Send new verification code
    3. Wait for user to provide code and 2FA password if needed
    4. Update session in database
    """
    try:
        account = await sync_to_async(TelegramAccount.objects.using('telegram_db').get)(id=account_id)

        logger.info(f"Starting reauthorization for account {account.phone_number} (ID: {account_id})")

        session_manager = SessionManager()
        account_data = await sync_to_async(session_manager.load_account_session)(account.phone_number)

        settings = await sync_to_async(GlobalAppSettings.objects.using('telegram_db').filter(is_active=True).first)()
        if not settings:
            return {"error": "Глобальные настройки приложения не настроены"}

        api_id, api_hash = settings.api_id, settings.api_hash

        client = TelegramClient(
            StringSession(),
            api_id,
            api_hash,
            device_model=f"CorporateManager_{platform.system()}",
            system_version=platform.version(),
            app_version="1.0",
            lang_code="ru",
            system_lang_code="ru"
        )

        await client.connect()

        try:
            result = await client.send_code_request(
                account.phone_number,
                force_sms=True
            )
            phone_code_hash = result.phone_code_hash
            logger.info(f"Phone code hash received: {phone_code_hash[:20]}...")

            session_string = client.session.save()
            session_data = session_string.encode('utf-8')

            await client.disconnect()

            success = await sync_to_async(session_manager.save_account_session)(
                phone_number=account.phone_number,
                session_data=session_data,
                recovery_email=account_data.get('recovery_email', ''),
                employee_id=account.employee_id,
                employee_fio=account.employee_fio,
                account_note=account.account_note,
                account_status='pending_reauthorization',
                phone_code_hash=phone_code_hash
            )

            if success:
                logger.info(f"Temporary session and phone_code_hash saved for {account.phone_number}")
                return {"message": f"Код подтверждения отправлен на {account.phone_number}. Используйте код верификации для завершения.", "requires_code": True}
            else:
                logger.error(f"Failed to save temporary session and phone_code_hash for {account.phone_number}")
                return {"error": "Не удалось сохранить данные для повторной авторизации"}

        except Exception as e:
            await client.disconnect()
            logger.error(f"Ошибка отправки кода для повторной авторизации: {e}")
            return {"error": f"Ошибка отправки кода: {str(e)}"}

    except Exception as e:
        logger.error(f"Ошибка повторной авторизации: {e}")
        return {"error": f"Ошибка: {str(e)}"}


def verify_reauthorization(account_id, code, two_factor_password=None):
    """Verify code for reauthorization"""
    try:
        return async_to_sync(_verify_reauthorization_async)(account_id, code, two_factor_password)
    except Exception as e:
        logger.error(f"Error in verify_reauthorization: {e}")
        raise
    finally:
        ThreadLocalDBConnection.close_all()


async def _verify_reauthorization_async(account_id, code, two_factor_password=None):
    try:
        account = await sync_to_async(TelegramAccount.objects.using('telegram_db').get)(id=account_id)

        logger.info(f"Verifying reauthorization code for {account.phone_number}")

        session_manager = SessionManager()
        account_data = await sync_to_async(session_manager.load_account_session)(account.phone_number)

        if not account_data['session_data']:
            return {"error": "Сессия не найдена. Пожалуйста, начните повторную авторизацию сначала."}

        session_data = account_data['session_data']
        if isinstance(session_data, memoryview):
            session_data = session_data.tobytes()
        session_string = session_data.decode('utf-8')

        settings = await sync_to_async(GlobalAppSettings.objects.using('telegram_db').filter(is_active=True).first)()
        if not settings:
            return {"error": "Глобальные настройки приложения не настроены"}

        api_id, api_hash = settings.api_id, settings.api_hash

        client = TelegramClient(
            StringSession(session_string),
            api_id,
            api_hash,
            device_model=f"CorporateManager_{platform.system()}",
            system_version=platform.version(),
            app_version="1.0",
            lang_code="ru",
            system_lang_code="ru"
        )

        await client.connect()

        # Если передан пароль 2FA, то пытаемся войти с паролем
        if two_factor_password:
            try:
                await client.sign_in(password=two_factor_password)
            except Exception as e:
                await client.disconnect()
                return {"error": f"Неверный пароль 2FA: {str(e)}"}
        else:
            # Вход с кодом подтверждения
            phone_code_hash = account_data.get('phone_code_hash')
            if not phone_code_hash:
                logger.warning(f"No phone_code_hash found for {account.phone_number}")
                return {"error": "Код подтверждения не был запрошен или истек. Пожалуйста, начните повторную авторизацию сначала."}

            try:
                await client.sign_in(
                    phone=account.phone_number,
                    code=code,
                    phone_code_hash=phone_code_hash
                )
            except PhoneCodeInvalidError:
                await client.disconnect()
                return {"error": "Неверный код подтверждения"}
            except PhoneCodeExpiredError:
                await client.disconnect()
                await sync_to_async(session_manager.clear_phone_code_hash)(account.phone_number)
                return {"error": "Код подтверждения истек. Пожалуйста, запросите новый код."}
            except SessionPasswordNeededError:
                await client.disconnect()
                return {"error": "Требуется пароль 2FA", "requires_2fa": True}
            except Exception as e:
                await client.disconnect()
                return {"error": f"Ошибка входа: {str(e)}"}

        # Если вход успешен (с кодом или паролем)
        new_session_string = client.session.save()
        new_session_data = new_session_string.encode('utf-8')

        success = await sync_to_async(session_manager.update_session)(
            phone_number=account.phone_number,
            new_session_data=new_session_data
        )

        await client.disconnect()

        if success:
            account.account_status = 'active'
            account.activity_status = 'active'
            await sync_to_async(account.save)()

            await sync_to_async(AccountAuditLog.objects.using('telegram_db').create)(
                account=account,
                action_type="reauthorization_completed",
                action_details={"reauthorized": True},
                performed_by="Система"
            )

            return {"message": f"Повторная авторизация успешно завершена для {account.phone_number}"}
        else:
            return {"error": "Не удалось сохранить новую сессию"}

    except Exception as e:
        logger.error(f"Ошибка верификации повторной авторизации: {e}")
        return {"error": f"Ошибка: {str(e)}"}


def check_api_credentials(api_id, api_hash):
    """Check if API credentials are valid"""
    try:
        return async_to_sync(_check_api_credentials_async)(api_id, api_hash)
    except Exception as e:
        logger.error(f"Error in check_api_credentials: {e}")
        raise
    finally:
        ThreadLocalDBConnection.close_all()


async def _check_api_credentials_async(api_id, api_hash):
    """Check if API credentials are valid by trying to connect"""
    try:
        client = TelegramClient(
            StringSession(),
            api_id,
            api_hash,
            device_model=f"CorporateManager_{platform.system()}",
            system_version=platform.version(),
            app_version="1.0",
            lang_code="ru",
            system_lang_code="ru"
        )

        await client.connect()

        try:
            await client.get_me()
            await client.disconnect()
            return True, "API credentials are valid"
        except Exception as e:
            await client.disconnect()
            return False, f"Invalid API credentials: {str(e)}"

    except Exception as e:
        return False, f"Connection error: {str(e)}"
