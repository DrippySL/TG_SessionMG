import os
import base64
import hashlib
import json
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Protocol.KDF import PBKDF2
from django.conf import settings


class EncryptionService:
    """
    Сервис для шифрования/дешифрования критических данных
    """
    
    def __init__(self, master_key=None):
        if master_key is None:
            master_key = settings.ENCRYPTION_KEY
        
        # Нормализуем ключ до 32 байт
        self.master_key = self._normalize_key(master_key)

    def _normalize_key(self, key_str):
        """Приводим ключ к 32 байтам (256 бит) для AES-256"""
        if isinstance(key_str, bytes):
            key_bytes = key_str
        else:
            key_bytes = key_str.encode('utf-8')
        
        # Используем SHA256 для получения 32 байт
        if len(key_bytes) != 32:
            key_bytes = hashlib.sha256(key_bytes).digest()
        
        # Если все еще не 32 байта, дополняем
        if len(key_bytes) < 32:
            key_bytes = key_bytes.ljust(32, b'\0')
        elif len(key_bytes) > 32:
            key_bytes = key_bytes[:32]
            
        return key_bytes

    def encrypt_data(self, plaintext: str) -> dict:
        """Шифрует данные с использованием AES-256-GCM"""
        # Генерируем случайный nonce (96 бит для GCM)
        nonce = get_random_bytes(12)

        # Создаем cipher
        cipher = AES.new(self.master_key, AES.MODE_GCM, nonce=nonce)

        # Шифруем данные
        ciphertext, tag = cipher.encrypt_and_digest(plaintext.encode('utf-8'))

        # Возвращаем все компоненты для хранения
        return {
            'nonce': base64.urlsafe_b64encode(nonce).decode('utf-8'),
            'ciphertext': base64.urlsafe_b64encode(ciphertext).decode('utf-8'),
            'tag': base64.urlsafe_b64encode(tag).decode('utf-8'),
            'version': 1
        }

    def decrypt_data(self, encrypted_data: dict) -> str:
        """Дешифрует данные"""
        nonce = base64.urlsafe_b64decode(encrypted_data['nonce'])
        ciphertext = base64.urlsafe_b64decode(encrypted_data['ciphertext'])
        tag = base64.urlsafe_b64decode(encrypted_data['tag'])

        cipher = AES.new(self.master_key, AES.MODE_GCM, nonce=nonce)
        plaintext = cipher.decrypt_and_verify(ciphertext, tag)

        return plaintext.decode('utf-8')

    @staticmethod
    def generate_master_key() -> str:
        """Генерирует мастер-ключ для шифрования"""
        key = base64.urlsafe_b64encode(os.urandom(32)).decode('utf-8')
        return key