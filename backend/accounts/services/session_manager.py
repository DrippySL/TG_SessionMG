import json
import base64
import hashlib
import logging
import threading
from datetime import datetime
from django.db import connections, transaction
from django.db.utils import DEFAULT_DB_ALIAS
from .encryption import EncryptionService
from ..models import GlobalAppSettings, ProxyServer

logger = logging.getLogger(__name__)


class ThreadLocalDBConnection:
    """Хранилище для соединений с базой данных, специфичных для потока"""
    _local = threading.local()
    
    @classmethod
    def get_connection(cls, alias='telegram_db'):
        if not hasattr(cls._local, 'connections'):
            cls._local.connections = {}
        
        if alias not in cls._local.connections:
            cls._local.connections[alias] = connections[alias]
        
        return cls._local.connections[alias]
    
    @classmethod
    def close_all(cls):
        if hasattr(cls._local, 'connections'):
            for alias, connection in cls._local.connections.items():
                try:
                    connection.close()
                except Exception:
                    pass
            cls._local.connections = {}


class SessionManager:
    """
    Управление Telegram сессиями: сохранение, загрузка, обновление
    Безопасный для использования в разных потоках
    """
    
    def __init__(self, encryption_service=None):
        self.encryptor = encryption_service or EncryptionService()
        
    def _get_db(self):
        """Получаем соединение с БД для текущего потока"""
        return ThreadLocalDBConnection.get_connection('telegram_db')
        
    def save_account_session(
        self,
        phone_number: str,
        session_data: bytes = None,
        recovery_email: str = None,
        employee_id: str = None,
        employee_fio: str = None,
        account_note: str = None,
        account_status: str = 'pending',
        phone_code_hash: str = None
    ) -> bool:
        """
        Сохраняет все критически важные данные аккаунта в БД
        Если session_data не передан, создается запись со статусом pending
        """
        try:
            logger.info(f"Saving account session for {phone_number}, status: {account_status}")
            
            settings = GlobalAppSettings.objects.using('telegram_db').filter(is_active=True).first()
            if not settings:
                raise ValueError("Global app settings not found")
            
            logger.info(f"Using global settings: API ID={settings.api_id}")
            
            encrypted_api_id = self.encryptor.encrypt_data(str(settings.api_id))
            encrypted_api_hash = self.encryptor.encrypt_data(settings.api_hash)
            
            if session_data:
                encrypted_session = self.encryptor.encrypt_data(
                    base64.urlsafe_b64encode(session_data).decode('utf-8')
                )
                session_hash = hashlib.sha256(session_data).hexdigest()
                logger.debug(f"Session hash generated: {session_hash[:20]}...")
            else:
                encrypted_session = self.encryptor.encrypt_data('')
                session_hash = ''
            
            if recovery_email:
                encrypted_recovery_email = self.encryptor.encrypt_data(recovery_email)
            else:
                encrypted_recovery_email = self.encryptor.encrypt_data('')
            
            if phone_code_hash is not None:
                encrypted_phone_code_hash = self.encryptor.encrypt_data(phone_code_hash)
                encrypted_phone_code_hash_bytes = json.dumps(encrypted_phone_code_hash).encode('utf-8')
                logger.debug(f"Phone code hash encrypted, length: {len(phone_code_hash)}")
            else:
                encrypted_phone_code_hash_bytes = None
                logger.debug("No phone code hash to save")

            db = self._get_db()
            with db.cursor() as cursor:
                query = """
                INSERT INTO telegram_accounts (
                    phone_number, employee_id, employee_fio, account_note,
                    encrypted_api_id, encrypted_api_hash,
                    encrypted_session, encrypted_recovery_email,
                    encrypted_phone_code_hash,
                    session_hash, session_updated_at, account_status, activity_status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (phone_number) DO UPDATE SET
                    employee_id = EXCLUDED.employee_id,
                    employee_fio = EXCLUDED.employee_fio,
                    account_note = EXCLUDED.account_note,
                    encrypted_api_id = EXCLUDED.encrypted_api_id,
                    encrypted_api_hash = EXCLUDED.encrypted_api_hash,
                    encrypted_session = EXCLUDED.encrypted_session,
                    encrypted_recovery_email = EXCLUDED.encrypted_recovery_email,
                    encrypted_phone_code_hash = EXCLUDED.encrypted_phone_code_hash,
                    session_hash = EXCLUDED.session_hash,
                    session_updated_at = EXCLUDED.session_updated_at,
                    account_status = EXCLUDED.account_status,
                    activity_status = 'active',
                    updated_at = NOW()
                """
                
                cursor.execute(query, (
                    phone_number,
                    employee_id,
                    employee_fio,
                    account_note,
                    json.dumps(encrypted_api_id).encode('utf-8'),
                    json.dumps(encrypted_api_hash).encode('utf-8'),
                    json.dumps(encrypted_session).encode('utf-8'),
                    json.dumps(encrypted_recovery_email).encode('utf-8'),
                    encrypted_phone_code_hash_bytes,
                    session_hash,
                    datetime.now(),
                    account_status,
                    'active'
                ))

            logger.info(f"Account session saved successfully for {phone_number}")
            
            self._log_audit(
                account_phone=phone_number,
                action_type="session_saved",
                details={"employee_id": employee_id, "employee_fio": employee_fio, "status": account_status}
            )

            return True

        except Exception as e:
            logger.error(f"Failed to save session for {phone_number}: {type(e).__name__}: {e}", exc_info=True)
            return False

    def get_phone_code_hash(self, phone_number: str) -> str:
        """Получает сохраненный phone_code_hash"""
        try:
            logger.debug(f"Getting phone code hash for {phone_number}")
            
            query = """
            SELECT encrypted_phone_code_hash
            FROM telegram_accounts
            WHERE phone_number = %s
            """
            
            db = self._get_db()
            with db.cursor() as cursor:
                cursor.execute(query, (phone_number,))
                result = cursor.fetchone()
                
            if not result or not result[0]:
                logger.warning(f"No phone code hash found for {phone_number}")
                raise ValueError(f"No phone code hash found for {phone_number}")
            
            encrypted_code_hash_bytes = result[0]
            if isinstance(encrypted_code_hash_bytes, memoryview):
                encrypted_code_hash_bytes = encrypted_code_hash_bytes.tobytes()
            
            encrypted_code_hash = json.loads(encrypted_code_hash_bytes.decode('utf-8'))
            phone_code_hash = self.encryptor.decrypt_data(encrypted_code_hash)
            logger.debug(f"Retrieved phone code hash: {phone_code_hash[:20]}...")
            return phone_code_hash
            
        except Exception as e:
            logger.error(f"Failed to get phone code hash for {phone_number}: {e}")
            raise
    
    def clear_phone_code_hash(self, phone_number: str) -> bool:
        """Очищает сохраненный phone_code_hash"""
        try:
            logger.debug(f"Clearing phone code hash for {phone_number}")
            
            query = """
            UPDATE telegram_accounts
            SET
                encrypted_phone_code_hash = NULL,
                updated_at = NOW()
            WHERE phone_number = %s
            """
            
            db = self._get_db()
            with db.cursor() as cursor:
                cursor.execute(query, (phone_number,))
                
            logger.info(f"Phone code hash cleared for {phone_number}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to clear phone code hash for {phone_number}: {e}")
            return False

    def load_account_session(self, phone_number: str) -> dict:
        """
        Загружает и дешифрует все данные аккаунта из БД
        """
        logger.info(f"Loading account session for {phone_number}")
        
        query = """
        SELECT
            encrypted_api_id,
            encrypted_api_hash,
            encrypted_session,
            encrypted_recovery_email,
            encrypted_phone_code_hash,
            session_hash,
            is_2fa_enabled,
            account_status
        FROM telegram_accounts
        WHERE phone_number = %s
        """

        db = self._get_db()
        with db.cursor() as cursor:
            cursor.execute(query, (phone_number,))
            result = cursor.fetchone()

        if not result:
            logger.error(f"Account {phone_number} not found in database")
            raise ValueError(f"Account {phone_number} not found")

        try:
            def to_bytes(data):
                if isinstance(data, memoryview):
                    return data.tobytes()
                elif isinstance(data, bytes):
                    return data
                else:
                    return data

            api_id_encrypted = to_bytes(result[0])
            api_id = int(self.encryptor.decrypt_data(json.loads(api_id_encrypted.decode('utf-8'))))
            
            api_hash_encrypted = to_bytes(result[1])
            api_hash = self.encryptor.decrypt_data(json.loads(api_hash_encrypted.decode('utf-8')))
            
            session_encrypted = to_bytes(result[2])
            if session_encrypted:
                session_b64 = self.encryptor.decrypt_data(json.loads(session_encrypted.decode('utf-8')))
                session_data = base64.urlsafe_b64decode(session_b64)
                logger.debug(f"Session data loaded, length: {len(session_data)} bytes")
            else:
                session_data = None
                logger.debug("No session data found")

            recovery_email_encrypted = to_bytes(result[3])
            recovery_email = self.encryptor.decrypt_data(json.loads(recovery_email_encrypted.decode('utf-8')))
            
            phone_code_hash_encrypted = to_bytes(result[4]) if result[4] else None
            if phone_code_hash_encrypted:
                phone_code_hash = self.encryptor.decrypt_data(json.loads(phone_code_hash_encrypted.decode('utf-8')))
                logger.debug(f"Phone code hash loaded: {phone_code_hash[:20]}...")
            else:
                phone_code_hash = None
                logger.debug("No phone code hash loaded")
            
            if session_data:
                current_hash = hashlib.sha256(session_data).hexdigest()
                if current_hash != result[5]:
                    logger.warning(f"Session hash mismatch for {phone_number}. Stored: {result[5][:20]}..., Calculated: {current_hash[:20]}...")
            else:
                current_hash = ''

            return {
                'api_id': api_id,
                'api_hash': api_hash,
                'session_data': session_data,
                'recovery_email': recovery_email,
                'phone_code_hash': phone_code_hash,
                'session_hash': result[5],
                'is_2fa_enabled': result[6],
                'account_status': result[7]
            }

        except Exception as e:
            logger.error(f"Failed to decrypt data for {phone_number}: {type(e).__name__}: {e}", exc_info=True)
            raise

    def update_session(self, phone_number: str, new_session_data: bytes) -> bool:
        """Обновляет сессию в БД"""
        try:
            logger.info(f"Updating session for {phone_number}")
            
            encrypted_session = self.encryptor.encrypt_data(
                base64.urlsafe_b64encode(new_session_data).decode('utf-8')
            )
            new_hash = hashlib.sha256(new_session_data).hexdigest()
            
            logger.debug(f"New session hash: {new_hash[:20]}...")

            query = """
            UPDATE telegram_accounts
            SET
                encrypted_session = %s,
                encrypted_phone_code_hash = NULL,
                session_hash = %s,
                session_updated_at = NOW(),
                account_status = 'active',
                activity_status = 'active',
                last_ping = NOW(),
                updated_at = NOW()
            WHERE phone_number = %s
            """

            db = self._get_db()
            with db.cursor() as cursor:
                cursor.execute(query, (
                    json.dumps(encrypted_session).encode('utf-8'),
                    new_hash,
                    phone_number
                ))

            logger.info(f"Session updated successfully for {phone_number}")
            
            self._log_audit(
                account_phone=phone_number,
                action_type="session_updated",
                details={"reason": "verification_completed"}
            )

            return True

        except Exception as e:
            logger.error(f"Failed to update session for {phone_number}: {e}")
            return False

    def delete_session(self, phone_number: str) -> bool:
        """Удаляет сессию из БД"""
        try:
            logger.info(f"Deleting session for {phone_number}")
            
            query = """
            UPDATE telegram_accounts
            SET
                encrypted_session = %s,
                encrypted_phone_code_hash = NULL,
                session_hash = %s,
                session_updated_at = NOW(),
                activity_status = 'dead',
                updated_at = NOW()
            WHERE phone_number = %s
            """
            
            db = self._get_db()
            with db.cursor() as cursor:
                cursor.execute(query, (
                    json.dumps({}).encode('utf-8'),
                    '',
                    phone_number
                ))
            
            logger.info(f"Session deleted for {phone_number}")
            
            self._log_audit(
                account_phone=phone_number,
                action_type="session_deleted",
                details={}
            )
            return True
        except Exception as e:
            logger.error(f"Failed to delete session for {phone_number}: {e}")
            return False

    def _log_audit(self, account_phone: str, action_type: str, details: dict):
        """Логирует действия в таблицу аудита"""
        query = """
        INSERT INTO account_audit_log (account_id, action_type, action_details)
        SELECT id, %s, %s
        FROM telegram_accounts
        WHERE phone_number = %s
        """
        
        db = self._get_db()
        with db.cursor() as cursor:
            cursor.execute(query, (action_type, json.dumps(details), account_phone))
    
    def close_all_connections(self):
        """Закрывает все соединения для текущего потока"""
        ThreadLocalDBConnection.close_all()
