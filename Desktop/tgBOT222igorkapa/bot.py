#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Бот для мониторинга криптовалютного рынка и отправки BUY-сигналов
"""

import time
import sys
from datetime import datetime
from config import CHECK_INTERVAL, BIT2ME_BASE_URL
from state_manager import StateManager
from market_monitor import MarketMonitor
from telegram_sender import TelegramSender

# Отключаем буферизацию для вывода в реальном времени
import functools
print = functools.partial(print, flush=True)


class CryptoSignalBot:
    """Главный класс бота"""
    
    def __init__(self):
        self.state_manager = StateManager()
        self.market_monitor = MarketMonitor()
        self.telegram = TelegramSender()
        self.running = False
    
    def start(self):
        """Запуск бота"""
        print("="*60)
        print("  CRYPTO SIGNAL BOT STARTED")
        print("="*60)
        
        # Получаем список пар для мониторинга
        print("\n[*] Getting trading pairs from Bit2Me...")
        pairs = self.market_monitor.filter_pairs()
        
        if not pairs:
            print("[ERROR] Could not get pairs list. Exiting.")
            return
        
        print(f"\n[OK] Monitoring {len(pairs)} pairs")
        print(f"[*] Check interval: {CHECK_INTERVAL} sec\n")
        
        # Отправляем статус в канал
        self.telegram.send_status(
            f"🤖 <b>Bot Started</b>\n\n"
            f"📊 Monitoring: <b>{len(pairs)}</b> EUR pairs\n"
            f"⏱ Interval: {CHECK_INTERVAL} sec\n"
            f"📈 Levels: -8%, -12%, -16%, -20%, -24%\n"
            f"🕐 {datetime.now().strftime('%H:%M:%S %d.%m.%Y')}"
        )
        
        self.running = True
        self.main_loop(pairs)
    
    def main_loop(self, pairs: list):
        """Основной цикл мониторинга"""
        cycle = 0
        
        while self.running:
            try:
                cycle += 1
                current_time = time.time()
                print(f"\n{'='*60}")
                print(f"  CYCLE #{cycle} | {datetime.now().strftime('%H:%M:%S')}")
                print(f"{'='*60}")
                
                # КРИТИЧЕСКИ ВАЖНО: Перезагружаем состояние из файла в начале каждого цикла
                # Это гарантирует, что triggered_levels синхронизирован с файлом между циклами
                # (защита от рассинхронизации памяти и файла)
                # Используем silent=True чтобы не спамить в лог каждый цикл
                self.state_manager.load_states(silent=True)
                
                # Обновляем цены одним запросом
                price_stats = self.market_monitor.refresh_prices()
                if not price_stats:
                    print("[ERROR] Failed to refresh prices, skipping cycle")
                    time.sleep(CHECK_INTERVAL)
                    continue
                
                # РАБОТАЕМ ТОЛЬКО С ПАРАМИ, ДЛЯ КОТОРЫХ API ВЕРНУЛ ДАННЫЕ!
                available_pairs = list(self.market_monitor.prices_cache.keys())
                
                if len(available_pairs) != len(pairs):
                    missing_count = len(pairs) - len(available_pairs)
                    print(f"[WARNING] API returned data for {len(available_pairs)}/{len(pairs)} pairs ({missing_count} missing)")
                    # Обновляем список пар на основе реальных данных от API
                    pairs = available_pairs
                
                print(f"[OK] Processing {len(pairs)} pairs with valid API data")
                
                # Собираем все сигналы за цикл
                cycle_signals = []
                sent_pairs = set()  # Защита от дубликатов в одном цикле
                checked_count = 0
                skipped_count = 0
                stats = {
                    "processed": 0,
                    "no_price": 0,
                    "init": 0,
                    "max_updated": 0,
                    "monitoring": 0
                }
                
                for pair in pairs:
                    try:
                        checked_count += 1
                        # Проверяем наличие цены перед обработкой
                        if self.market_monitor.get_current_price(pair) is None:
                            stats["no_price"] += 1
                            continue
                        
                        stats["processed"] += 1
                        result = self.check_pair(pair, current_time, stats)
                        signal = result if isinstance(result, dict) else None
                        if signal and pair not in sent_pairs:
                            cycle_signals.append(signal)
                            sent_pairs.add(pair)
                        elif signal:
                            skipped_count += 1  # Дубликат в одном цикле
                    except Exception as e:
                        print(f"[ERROR] Processing {pair}: {e}")
                
                # Подсчёт пар с падениями
                drops_count = sum(1 for p in pairs if self.market_monitor.get_current_price(p) is not None)
                
                print(f"\n[STATS] Checked: {checked_count}/{len(pairs)} total")
                print(f"        Processed: {stats['processed']}, No price: {stats['no_price']}")
                print(f"        New: {stats['init']}, Max updated: {stats['max_updated']}, Monitoring: {stats['monitoring']}")
                print(f"        Signals: {len(cycle_signals)}, Skipped duplicates: {skipped_count}")
                
                # ДЕТАЛЬНОЕ ЛОГИРОВАНИЕ: падение/рост от local_max для всех пар (ПОСЛЕ обработки)
                drops_from_max = []
                for pair in pairs:
                    try:
                        current_price = self.market_monitor.get_current_price(pair)
                        if current_price is None:
                            continue
                        
                        state = self.state_manager.get_state(pair)
                        local_max = state.get("local_max")
                        
                        if local_max is not None and local_max > 0:
                            change_from_max = ((current_price - local_max) / local_max) * 100
                            drops_from_max.append({
                                "pair": pair,
                                "price": current_price,
                                "local_max": local_max,
                                "change": change_from_max,
                                "levels": state.get("triggered_levels", [])
                            })
                    except Exception as e:
                        print(f"[ERROR] Processing {pair} for max logging: {e}")
                
                # Сортируем по падению (от большего падения к меньшему, потом рост)
                drops_from_max.sort(key=lambda x: x["change"])
                
                # Выводим все пары с их падением/ростом от local_max
                print(f"\n{'='*80}")
                print(f"PRICE vs LOCAL_MAX (after processing) | Total: {len(drops_from_max)}")
                print(f"{'='*80}")
                
                for idx, info in enumerate(drops_from_max, 1):
                    try:
                        pair = info["pair"]
                        price = info["price"]
                        max_price = info["local_max"]
                        change = info["change"]
                        levels = info["levels"]
                        
                        price_str = f"{price:.8f}" if price < 1 else f"{price:.4f}"
                        max_str = f"{max_price:.8f}" if max_price < 1 else f"{max_price:.4f}"
                        change_str = f"{change:+.4f}%"
                        
                        # Учитываем погрешность float: считаем "на максимуме" если изменение меньше 0.01%
                        if change < -0.01:  # Падение больше 0.01%
                            symbol = "[DROP]"
                            levels_str = f"L{levels}" if levels else "[]"
                            print(f"{idx:3d}. {pair:15s} price={price_str:>12s} | max={max_str:>12s} | {symbol} {change_str:>10s} | levels={levels_str}")
                        elif change > 0.01:  # Рост больше 0.01%
                            symbol = "[RISE]"
                            print(f"{idx:3d}. {pair:15s} price={price_str:>12s} | max={max_str:>12s} | {symbol} {change_str:>10s} | [above max]")
                        else:  # Изменение меньше 0.01% - считаем на максимуме
                            symbol = "[MAX]"
                            print(f"{idx:3d}. {pair:15s} price={price_str:>12s} | max={max_str:>12s} | {symbol} {change_str:>10s}")
                    except Exception as e:
                        print(f"[ERROR] Printing max change for {info.get('pair', 'UNKNOWN')}: {e}")
                
                print(f"{'='*80}\n")
                
                # Показываем пары с наибольшим падением (топ-5) с детальной информацией
                drops_info = []
                for p in pairs:
                    price = self.market_monitor.get_current_price(p)
                    if price:
                        st = self.state_manager.get_state(p)
                        if st.get("local_max") and st["local_max"] > 0:
                            drop = ((price - st["local_max"]) / st["local_max"]) * 100
                            if drop < 0:  # Только падения
                                last_price = st.get("last_price")
                                price_change = ((price - last_price) / last_price * 100) if last_price and last_price > 0 else 0
                                drops_info.append((p, drop, price, st["local_max"], st.get("triggered_levels", []), last_price, price_change))
                
                if drops_info:
                    drops_info.sort(key=lambda x: x[1])  # Сортируем по падению (меньше = больше падение)
                    print(f"\n[TOP DROPS] (vs local_max)")
                    for idx, (pair, drop, price, max_price, levels, last_price, price_change) in enumerate(drops_info[:5], 1):
                        levels_str = f"L{levels}" if levels else "[]"
                        last_str = f"{last_price:.4f}" if last_price else "N/A"
                        change_str = f"{price_change:+.2f}%" if last_price and last_price > 0 else "N/A"
                        print(f"  {idx}. {pair}: {drop:.2f}% drop | price={price:.4f} (was {last_str} {change_str}) | max={max_price:.4f} | levels={levels_str}")
                
                # Отправляем сигналы (уровни уже сохранены в check_pair() СРАЗУ после создания)
                # НЕ проверяем is_duplicate_signal() здесь, т.к. это уже сделано в check_pair() ДО сохранения уровня!
                # Если бы проверять здесь - сигнал будет заблокирован, т.к. уровень уже в triggered_levels
                if cycle_signals:
                    print(f"\n[SENDING] Preparing to send {len(cycle_signals)} signals (levels already saved in check_pair)")
                    for sig in cycle_signals:
                        print(f"  - {sig['pair']}: Level {sig['level']}, drop {sig['drop_percent']:.2f}%, price {sig.get('current_price', 'N/A')}")
                    
                    result = self.telegram.send_signals_batch(cycle_signals, self.market_monitor)
                    if result:
                        print(f"[SIGNALS SENT] ✅ Successfully sent {len(cycle_signals)} signals")
                    else:
                        print(f"[SIGNALS SENT] ❌ Failed to send signals (result={result})")
                else:
                    print(f"[SENDING] No signals to send (cycle_signals is empty)")
                
                print(f"\n[OK] Cycle complete. Waiting {CHECK_INTERVAL} sec...")
                time.sleep(CHECK_INTERVAL)
                
            except KeyboardInterrupt:
                print("\n\n[!] Stop signal received...")
                self.stop()
                break
            except Exception as e:
                print(f"\n[CRITICAL] Error in main loop: {e}")
                time.sleep(1)  # Минимальная задержка при ошибке
    
    def check_pair(self, pair: str, current_time: float, stats: dict = None):
        """Проверка одной торговой пары. Возвращает signal dict или None"""
        # Получаем текущую цену
        current_price = self.market_monitor.get_current_price(pair)
        if current_price is None:
            return None
        
        # Получаем состояние пары
        state = self.state_manager.get_state(pair)
        
        # Инициализация локального максимума
        if state["local_max"] is None:
            self.state_manager.update_state(
                pair,
                local_max=current_price,
                local_max_time=current_time,
                local_min=current_price,
                last_price=current_price,
                initialized=True,  # Сразу инициализирована, начинает мониторинг
                initialization_time=current_time
            )
            if stats is not None:
                stats["init"] += 1
            return None
        
        # Проверка возраста локального максимума (4 часа)
        if self.state_manager.check_local_max_age(pair, current_time):
            self.state_manager.reset_state(pair, current_price)
            # Очищаем кэш сообщений для этой пары при RESET
            self.telegram.clear_cache_for_pair(pair)
            return None
        
        # Проверка условий для RESET
        if self.state_manager.should_reset(pair, current_price, current_time):
            self.state_manager.reset_state(pair, current_price)
            # Очищаем кэш сообщений для этой пары при RESET
            self.telegram.clear_cache_for_pair(pair)
            return None
        
        # Обновление локального максимума (если цена выше более чем на 0.01%)
        # ВАЖНО: Обновление максимума НЕ вызывает RESET!
        # RESET происходит ТОЛЬКО через should_reset():
        #   - Рост от минимума на нужный % (зависит от уровня)
        #   - ИЛИ через 2 часа после последнего сигнала
        price_increase = ((current_price - state["local_max"]) / state["local_max"]) * 100 if state["local_max"] > 0 else 0
        if price_increase > 0.01:  # Рост больше 0.01% - обновляем максимум
            print(f"[MAX UPDATE] {pair}: {state['local_max']:.4f} -> {current_price:.4f} (+{price_increase:.2f}%) | triggered_levels сохранены: {state.get('triggered_levels', [])}")
            self.state_manager.update_state(
                pair,
                local_max=current_price,
                local_max_time=current_time,
                # НЕ обновляем local_min и НЕ обнуляем triggered_levels - это НЕ RESET!
                # triggered_levels и local_min остаются для проверки RESET через should_reset()
                last_price=current_price
            )
            if stats is not None:
                stats["max_updated"] += 1
            # НЕ return None - продолжаем проверку уровней, так как RESET не произошёл
            # (хотя сейчас уровни не должны сработать, так как цена выше максимума)
        
        # Обновление локального минимума (если цена ниже)
        if state["local_min"] is None or current_price < state["local_min"]:
            self.state_manager.update_state(
                pair,
                local_min=current_price,
                last_price=current_price
            )
        
        # Проверка уровней падения (получаем актуальное состояние)
        # КРИТИЧЕСКИ ВАЖНО: Перезагружаем состояние из файла перед проверкой уровней
        # Это гарантирует, что triggered_levels синхронизирован с файлом
        self.state_manager.load_states(silent=True)
        current_state = self.state_manager.get_state(pair)
        
        # Вычисляем падение для логирования
        drop_percent = ((current_price - current_state["local_max"]) / current_state["local_max"]) * 100 if current_state["local_max"] and current_state["local_max"] > 0 else 0
        
        # Логируем пары с значительным падением (>3%)
        if drop_percent <= -3.0:
            print(f"[DROP] {pair}: {drop_percent:.2f}% | price={current_price:.4f}, max={current_state['local_max']:.4f}, triggered={current_state['triggered_levels']}")
        
        triggered_levels = current_state.get("triggered_levels", [])
        
        signal = self.market_monitor.check_levels(
            pair,
            current_price,
            current_state["local_max"],
            triggered_levels  # Используем актуальный список
        )
        
        # Подсчёт мониторинга (пара инициализирована и активно мониторится, нет сигналов)
        if stats is not None and not signal and current_state.get("initialized", False):
            stats["monitoring"] += 1
        
        # ВАЖНО: ВСЕГДА обновляем last_price для отслеживания изменений между циклами
        if current_state.get("last_price") != current_price:
            self.state_manager.update_state(pair, last_price=current_price)
        
        if signal:
            level = signal["level"]
            drop = signal["drop_percent"]
            
            # КРИТИЧЕСКИ ВАЖНО: Проверяем ЕЩЁ РАЗ, что уровень не сработал (финальная проверка)
            # Перезагружаем состояние ЕЩЁ РАЗ перед финальной проверкой
            self.state_manager.load_states(silent=True)
            final_check = self.state_manager.get_state(pair)
            triggered_in_check = final_check.get("triggered_levels", [])
            
            if level in triggered_in_check:
                print(f"[SKIP DUPLICATE] {pair}: Level {level} already in triggered_levels: {triggered_in_check} | drop={drop:.2f}%")
                return None
            
            # УБИРАЕМ ВРЕМЕННОЕ ОКНО: сохраняем уровень СРАЗУ после создания сигнала, ДО возврата
            # Это гарантирует, что следующий цикл уже увидит уровень в triggered_levels
            # Нет race condition между созданием и сохранением!
            self.state_manager.add_triggered_level(pair, level, current_time)
            
            # ФИНАЛЬНАЯ ПРОВЕРКА: убеждаемся, что уровень действительно сохранён
            verify_state = self.state_manager.get_state(pair)
            if level not in verify_state.get("triggered_levels", []):
                print(f"[ERROR] {pair}: Level {level} NOT saved to triggered_levels! State: {verify_state.get('triggered_levels', [])}")
                # Пытаемся сохранить ещё раз
                self.state_manager.add_triggered_level(pair, level, current_time)
            
            # КРИТИЧЕСКИ ВАЖНО: Проверяем, что цена валидна перед отправкой
            if current_price is None or current_price <= 0:
                print(f"[ERROR] {pair}: Invalid price ({current_price}) when creating signal! Getting fresh price from cache...")
                # Пытаемся получить актуальную цену из кэша
                fresh_price = self.market_monitor.get_current_price(pair)
                if fresh_price is not None and fresh_price > 0:
                    current_price = fresh_price
                    print(f"[FIXED] {pair}: Updated price to {current_price:.4f}")
                else:
                    print(f"[ERROR] {pair}: Still invalid price ({fresh_price}), using fallback")
                    # Используем local_max как fallback
                    if current_state.get("local_max") and current_state["local_max"] > 0:
                        current_price = current_state["local_max"]
                        print(f"[FALLBACK] {pair}: Using local_max as price: {current_price:.4f}")
            
            print(f"[SIGNAL CREATED] {pair}: Level {level} | {drop:.2f}% | Price: {current_price:.4f} | triggered_levels={verify_state.get('triggered_levels', [])}")
            
            # Возвращаем сигнал для отправки батчем
            return {
                "pair": pair,
                "drop_percent": drop,
                "level": level,
                "current_price": current_price  # Добавляем текущую цену для отображения в сообщении
            }
        else:
            return None
    
    def stop(self):
        """Остановка бота"""
        print("\n[*] Stopping bot...")
        self.running = False
        self.state_manager.save_states()
        self.telegram.send_status(
            f"⛔ Bot stopped\n"
            f"🕐 {datetime.now().strftime('%H:%M:%S %d.%m.%Y')}"
        )
        print("[OK] Bot stopped")


def main():
    """Точка входа"""
    bot = CryptoSignalBot()
    try:
        bot.start()
    except Exception as e:
        print(f"\n[CRITICAL] Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
