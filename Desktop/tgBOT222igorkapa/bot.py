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
            f"📈 Signals: -8% от максимума, затем каждые -2% от последнего сигнала\n"
            f"🔄 RESET: 24 часа ИЛИ +7% от минимума\n"
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
                # КРИТИЧЕСКИ ВАЖНО: Фильтруем только пары из MONITORED_PAIRS, 
                # а не все пары из prices_cache (который теперь содержит только мониторируемые пары)
                available_pairs_from_cache = set(self.market_monitor.prices_cache.keys())
                filtered_pairs = [p for p in pairs if p in available_pairs_from_cache]
                
                if len(filtered_pairs) != len(pairs):
                    missing_count = len(pairs) - len(filtered_pairs)
                    print(f"[WARNING] API returned data for {len(filtered_pairs)}/{len(pairs)} pairs ({missing_count} missing)")
                    pairs = filtered_pairs
                
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
                                "last_level": state.get("last_signal_level")
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
                        last_level = info["last_level"]
                        
                        price_str = f"{price:.8f}" if price < 1 else f"{price:.4f}"
                        max_str = f"{max_price:.8f}" if max_price < 1 else f"{max_price:.4f}"
                        change_str = f"{change:+.4f}%"
                        level_str = f"L{last_level}" if last_level else "[]"
                        
                        # Учитываем погрешность float: считаем "на максимуме" если изменение меньше 0.01%
                        if change < -0.01:  # Падение больше 0.01%
                            symbol = "[DROP]"
                            print(f"{idx:3d}. {pair:15s} price={price_str:>12s} | max={max_str:>12s} | {symbol} {change_str:>10s} | level={level_str}")
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
                                drops_info.append((p, drop, price, st["local_max"], st.get("last_signal_level"), last_price, price_change))
                
                if drops_info:
                    drops_info.sort(key=lambda x: x[1])  # Сортируем по падению (меньше = больше падение)
                    print(f"\n[TOP DROPS] (vs local_max)")
                    for idx, (pair, drop, price, max_price, last_level, last_price, price_change) in enumerate(drops_info[:5], 1):
                        level_str = f"L{last_level}" if last_level else "[]"
                        last_str = f"{last_price:.4f}" if last_price else "N/A"
                        change_str = f"{price_change:+.2f}%" if last_price and last_price > 0 else "N/A"
                        print(f"  {idx}. {pair}: {drop:.2f}% drop | price={price:.4f} (was {last_str} {change_str}) | max={max_price:.4f} | level={level_str}")
                
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
        
        # Проверка условий для RESET
        if self.state_manager.should_reset(pair, current_price, current_time):
            self.state_manager.reset_state(pair, current_price)
            # Очищаем кэш сообщений для этой пары при RESET
            self.telegram.clear_cache_for_pair(pair)
            return None
        
        # Обновление локального максимума (если цена выше)
        if current_price > state["local_max"]:
            print(f"[MAX UPDATE] {pair}: {state['local_max']:.4f} -> {current_price:.4f}")
            self.state_manager.update_state(
                pair,
                local_max=current_price,
                local_max_time=current_time,
                last_price=current_price
            )
            if stats is not None:
                stats["max_updated"] += 1
        
        # Обновление локального минимума (если цена ниже)
        if state["local_min"] is None or current_price < state["local_min"]:
            self.state_manager.update_state(
                pair,
                local_min=current_price,
                last_price=current_price
            )
        
        # НОВАЯ ЛОГИКА ПРОВЕРКИ УРОВНЕЙ
        # Перезагружаем состояние для синхронизации
        self.state_manager.load_states(silent=True)
        current_state = self.state_manager.get_state(pair)
        
        # Обновляем last_price
        if current_state.get("last_price") != current_price:
            self.state_manager.update_state(pair, last_price=current_price)
        
        # Вычисляем падение от local_max для логирования
        drop_from_max = ((current_price - current_state["local_max"]) / current_state["local_max"]) * 100
        
        # Логируем пары с падением >3%
        if drop_from_max <= -3.0:
            last_signal_price = current_state.get("last_signal_price")
            last_level = current_state.get("last_signal_level")
            signal_info = f"last_signal: level={last_level}, price={last_signal_price:.4f}" if last_signal_price else "no signals yet"
            print(f"[DROP] {pair}: {drop_from_max:.2f}% | price={current_price:.4f}, max={current_state['local_max']:.4f} | {signal_info}")
        
        # Проверяем условия для сигнала
        signal = None
        last_signal_price = current_state.get("last_signal_price")
        last_signal_level = current_state.get("last_signal_level")
        
        if last_signal_price is None:
            # Ещё не было сигналов - проверяем первый уровень (-8% от local_max)
            from config import FIRST_SIGNAL_DROP
            if drop_from_max <= FIRST_SIGNAL_DROP:
                signal = {
                    "pair": pair,
                    "level": 1,
                    "drop_percent": drop_from_max,
                    "current_price": current_price
                }
                print(f"[SIGNAL] {pair}: FIRST signal (level 1) | {drop_from_max:.2f}% | price={current_price:.4f}")
        else:
            # Уже были сигналы - проверяем падение от last_signal_price
            drop_from_last_signal = ((current_price - last_signal_price) / last_signal_price) * 100
            
            # Сколько уровней по -2% прошли?
            from config import NEXT_SIGNAL_DROP
            levels_passed = int(abs(drop_from_last_signal / abs(NEXT_SIGNAL_DROP)))
            
            if levels_passed > 0:
                # Прошли один или несколько уровней - отправляем только последний
                new_level = last_signal_level + levels_passed
                signal = {
                    "pair": pair,
                    "level": new_level,
                    "drop_percent": drop_from_max,  # Падение от максимума для отображения
                    "current_price": current_price
                }
                print(f"[SIGNAL] {pair}: NEXT signal (level {new_level}) | {drop_from_last_signal:.2f}% from last_signal | total {drop_from_max:.2f}% from max | levels_passed={levels_passed}")
        
        if signal:
            # Сохраняем сигнал
            self.state_manager.update_signal(
                pair,
                signal["level"],
                current_price,
                current_time
            )
            
            # Подсчёт статистики
            if stats is not None:
                stats["monitoring"] += 1
            
            return signal
        else:
            # Подсчёт мониторинга
            if stats is not None and current_state.get("initialized", False):
                stats["monitoring"] += 1
            
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
