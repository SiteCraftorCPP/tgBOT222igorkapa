#!/usr/bin/env python3
# Тестовый скрипт для проверки путей и импортов

import sys
import os

print("=" * 60)
print("PATH CHECK FOR DEPLOYMENT")
print("=" * 60)

# Проверка текущей директории
print(f"\n[1] Current directory: {os.getcwd()}")

# Проверка наличия файлов
required_files = [
    "bot.py",
    "config.py",
    "state_manager.py",
    "market_monitor.py",
    "telegram_sender.py",
    "requirements.txt"
]

print("\n[2] Checking required files:")
all_ok = True
for file in required_files:
    exists = os.path.exists(file)
    status = "✅" if exists else "❌"
    print(f"  {status} {file}")
    if not exists:
        all_ok = False

# Проверка импортов
print("\n[3] Checking imports:")
try:
    from config import STATE_FILE, CHECK_INTERVAL, LEVELS
    print(f"  ✅ config.py imported")
    print(f"     STATE_FILE: {STATE_FILE}")
    print(f"     CHECK_INTERVAL: {CHECK_INTERVAL}")
    print(f"     LEVELS: {len(LEVELS)} levels configured")
except Exception as e:
    print(f"  ❌ config.py import failed: {e}")
    all_ok = False

try:
    from state_manager import StateManager
    print(f"  ✅ state_manager.py imported")
except Exception as e:
    print(f"  ❌ state_manager.py import failed: {e}")
    all_ok = False

try:
    from market_monitor import MarketMonitor
    print(f"  ✅ market_monitor.py imported")
except Exception as e:
    print(f"  ❌ market_monitor.py import failed: {e}")
    all_ok = False

try:
    from telegram_sender import TelegramSender
    print(f"  ✅ telegram_sender.py imported")
except Exception as e:
    print(f"  ❌ telegram_sender.py import failed: {e}")
    all_ok = False

# Проверка StateManager
print("\n[4] Testing StateManager:")
try:
    sm = StateManager()
    print(f"  ✅ StateManager initialized")
    print(f"     States loaded: {len(sm.states)} pairs")
except Exception as e:
    print(f"  ❌ StateManager failed: {e}")
    all_ok = False

# Проверка путей к файлам
print("\n[5] File paths:")
print(f"  STATE_FILE: {os.path.abspath(STATE_FILE) if 'STATE_FILE' in locals() else 'N/A'}")

print("\n" + "=" * 60)
if all_ok:
    print("✅ ALL CHECKS PASSED - Ready for deployment!")
else:
    print("❌ SOME CHECKS FAILED - Fix issues above")
print("=" * 60)

