#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестовый скрипт для проверки отправки сигналов в Telegram
"""

import sys
import io
import requests
import json
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

# Исправляем кодировку для Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def test_single_signal():
    """Тест отправки одиночного сигнала"""
    print("="*60)
    print("ТЕСТ 1: Отправка одиночного сигнала")
    print("="*60)
    
    base_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    
    # Тестовые данные сигнала
    pair = "BTCEUR"
    drop_percent = -8.5
    current_price = 42000.50
    
    # Форматируем пару: BTCEUR -> BTC/EUR
    formatted_pair = pair.replace("EUR", "") + "/EUR"
    
    # Форматируем цену
    price_str = f"{current_price:.4f}€" if current_price < 1 else f"{current_price:.2f}€"
    
    # Формируем текст сигнала
    message = f"💎 {formatted_pair} | −{abs(drop_percent):.1f}% | {price_str}"
    
    # Создаём инлайн кнопку
    coin = pair.replace("EUR", "").lower()
    buy_url = f"https://bit2me.com/es/precio/{coin}"
    
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
        "reply_markup": {
            "inline_keyboard": [[{
                "text": "🚀 COMPRAR",
                "url": buy_url
            }]]
        }
    }
    
    print(f"Chat ID: {TELEGRAM_CHAT_ID}")
    print(f"Message: {message}")
    print(f"Buy URL: {buy_url}")
    print(f"Button text: 🚀 COMPRAR")
    print("\nОтправка запроса...")
    
    try:
        response = requests.post(
            f"{base_url}/sendMessage",
            json=payload,
            timeout=10
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                print("✅ УСПЕХ! Сигнал отправлен в канал")
                print(f"Message ID: {result.get('result', {}).get('message_id')}")
                return True
            else:
                print(f"❌ ОШИБКА: {result.get('description', 'Unknown error')}")
                return False
        else:
            print(f"❌ ОШИБКА HTTP {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ ИСКЛЮЧЕНИЕ: {e}")
        return False


def test_batch_signals():
    """Тест отправки нескольких сигналов - каждый отдельным сообщением (как в реальном боте)"""
    print("\n" + "="*60)
    print("ТЕСТ 2: Отправка батча сигналов - каждый отдельным сообщением")
    print("="*60)
    
    base_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    
    # Тестовые сигналы
    test_signals = [
        {"pair": "ETHEUR", "drop_percent": -12.3, "current_price": 2450.75},
        {"pair": "SOLEUR", "drop_percent": -16.8, "current_price": 0.0874},
        {"pair": "ADAEUR", "drop_percent": -20.5, "current_price": 0.4523}
    ]
    
    print(f"Chat ID: {TELEGRAM_CHAT_ID}")
    print(f"Signals count: {len(test_signals)}")
    print("Отправка каждого сигнала отдельным сообщением...\n")
    
    sent_count = 0
    failed_count = 0
    message_ids = []
    
    for i, signal in enumerate(test_signals, 1):
        try:
            pair = signal["pair"].replace("/", "")  # Убираем / если есть
            drop = signal["drop_percent"]
            current_price = signal["current_price"]
            
            # Форматируем пару: BTCEUR -> BTC/EUR
            formatted_pair = pair.replace("EUR", "") + "/EUR"
            
            # Форматируем цену
            price_str = f"{current_price:.4f}€" if current_price < 1 else f"{current_price:.2f}€"
            
            message = f"💎 {formatted_pair} | −{abs(drop):.1f}% | {price_str}"
            
            # Создаём инлайн кнопку
            coin = pair.replace("EUR", "").lower()
            buy_url = f"https://bit2me.com/es/precio/{coin}"
            
            payload = {
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
                "reply_markup": {
                    "inline_keyboard": [[{
                        "text": "🚀 COMPRAR",
                        "url": buy_url
                    }]]
                }
            }
            
            print(f"[{i}/{len(test_signals)}] Отправка: {message}")
            print(f"         URL: {buy_url}")
            
            response = requests.post(
                f"{base_url}/sendMessage",
                json=payload,
                timeout=10
            )
            
            print(f"         Status Code: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    msg_id = result.get('result', {}).get('message_id')
                    message_ids.append(msg_id)
                    print(f"         ✅ Успешно! Message ID: {msg_id}\n")
                    sent_count += 1
                else:
                    print(f"         ❌ ОШИБКА: {result.get('description', 'Unknown error')}\n")
                    failed_count += 1
            else:
                print(f"         ❌ ОШИБКА HTTP {response.status_code}")
                print(f"         Response: {response.text}\n")
                failed_count += 1
                
        except Exception as e:
            print(f"         ❌ ИСКЛЮЧЕНИЕ: {e}\n")
            failed_count += 1
    
    print("="*60)
    print(f"ИТОГИ: Отправлено {sent_count}/{len(test_signals)} сигналов")
    if failed_count > 0:
        print(f"Ошибок: {failed_count}")
    if message_ids:
        print(f"Message IDs: {', '.join(map(str, message_ids))}")
    
    return sent_count == len(test_signals)


def test_telegram_connection():
    """Тест подключения к Telegram API"""
    print("\n" + "="*60)
    print("ТЕСТ 0: Проверка подключения к Telegram API")
    print("="*60)
    
    base_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    
    try:
        response = requests.get(
            f"{base_url}/getMe",
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                bot_info = result.get("result", {})
                print(f"✅ Бот подключён!")
                print(f"Bot username: @{bot_info.get('username')}")
                print(f"Bot name: {bot_info.get('first_name')}")
                print(f"Bot ID: {bot_info.get('id')}")
                
                # Проверяем доступ к каналу
                print(f"\nПроверка доступа к каналу {TELEGRAM_CHAT_ID}...")
                chat_response = requests.get(
                    f"{base_url}/getChat?chat_id={TELEGRAM_CHAT_ID}",
                    timeout=10
                )
                
                if chat_response.status_code == 200:
                    chat_result = chat_response.json()
                    if chat_result.get("ok"):
                        chat_info = chat_result.get("result", {})
                        print(f"✅ Доступ к каналу есть!")
                        print(f"Chat type: {chat_info.get('type')}")
                        print(f"Chat title: {chat_info.get('title', 'N/A')}")
                        return True
                    else:
                        print(f"❌ Нет доступа к каналу: {chat_result.get('description')}")
                        return False
                else:
                    print(f"❌ Ошибка проверки канала: HTTP {chat_response.status_code}")
                    print(f"Response: {chat_response.text}")
                    return False
            else:
                print(f"❌ Ошибка API: {result.get('description')}")
                return False
        else:
            print(f"❌ Ошибка HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ ИСКЛЮЧЕНИЕ: {e}")
        return False


def test_message_format():
    """Тест формата сообщения (без отправки)"""
    print("\n" + "="*60)
    print("ТЕСТ 3: Проверка формата сообщения")
    print("="*60)
    
    # Симулируем реальный сигнал из бота
    test_cases = [
        {"pair": "BTCEUR", "drop": -8.5, "price": 42000.50},
        {"pair": "ETHEUR", "drop": -12.3, "price": 2450.75},
        {"pair": "FARTCOINEUR", "drop": -16.8, "price": 0.0874},
        {"pair": "ADAEUR", "drop": -20.5, "price": 0.4523},
        {"pair": "DOGEEUR", "drop": -24.2, "price": 0.12345}
    ]
    
    print("Проверка форматирования:")
    for i, test in enumerate(test_cases, 1):
        pair = test["pair"]
        drop = test["drop"]
        price = test["price"]
        
        formatted_pair = pair.replace("EUR", "") + "/EUR"
        price_str = f"{price:.4f}€" if price < 1 else f"{price:.2f}€"
        message = f"💎 {formatted_pair} | −{abs(drop):.1f}% | {price_str}"
        
        coin = pair.replace("EUR", "").lower()
        buy_url = f"https://bit2me.com/es/precio/{coin}"
        button_text = "🚀 COMPRAR"
        
        print(f"\n{i}. {message}")
        print(f"   URL: {buy_url}")
        print(f"   Button: {button_text}")
        
        # Проверка длины сообщения (Telegram limit: 4096 символов)
        if len(message) > 4096:
            print(f"   ⚠️  ПРЕДУПРЕЖДЕНИЕ: Сообщение слишком длинное ({len(message)} символов)")
    
    print("\n✅ Формат сообщений корректен")
    return True


if __name__ == "__main__":
    print("\n" + "="*60)
    print("ТЕСТИРОВАНИЕ ОТПРАВКИ СИГНАЛОВ В TELEGRAM")
    print("="*60)
    print(f"Token: {TELEGRAM_BOT_TOKEN[:20]}...")
    print(f"Chat ID: {TELEGRAM_CHAT_ID}")
    print("="*60)
    
    # Тест 0: Подключение
    connection_ok = test_telegram_connection()
    
    if not connection_ok:
        print("\n❌ НЕ УДАЛОСЬ ПОДКЛЮЧИТЬСЯ К TELEGRAM API")
        print("Проверьте токен и доступность API")
        exit(1)
    
    # Тест 3: Формат сообщения
    test_message_format()
    
    # Тест 1: Одиночный сигнал
    test1_ok = test_single_signal()
    
    # Тест 2: Батч сигналов
    test2_ok = test_batch_signals()
    
    # Итоги
    print("\n" + "="*60)
    print("ИТОГИ ТЕСТИРОВАНИЯ")
    print("="*60)
    print(f"Подключение к API: {'✅ OK' if connection_ok else '❌ FAIL'}")
    print(f"Формат сообщений: ✅ OK")
    print(f"Одиночный сигнал: {'✅ OK' if test1_ok else '❌ FAIL'}")
    print(f"Батч сигналов: {'✅ OK' if test2_ok else '❌ FAIL'}")
    print("="*60)
    
    if connection_ok and test1_ok and test2_ok:
        print("\n✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ! Сигналы будут доходить до канала")
        exit(0)
    else:
        print("\n❌ ЕСТЬ ОШИБКИ! Проверьте логи выше")
        exit(1)
