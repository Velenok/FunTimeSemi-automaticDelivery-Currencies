

import ssl
import customtkinter as ctk
import tkinter.messagebox as messagebox
from tkinter import simpledialog
import threading
import time
import sys
import json
import os
from io import BytesIO
from PIL import Image
import logging
import asyncio
import random

from telegram import Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

try:
    import keyboard
except ImportError:
    keyboard = None
try:
    import pyautogui
except ImportError:
    pyautogui = None

CONFIG_FILE = "config.json"
LOG_FILE = "app.log"


DEFAULT_CONFIG = {
    "token": "",
    "delays": [3, 2.5, 0.5],
    "an_command": "/an605",
    "esc_delay": 0.3,
    "screenshot_delay": 2.0,
    "anti_afk_enabled": False,
    "anti_afk_hotkey": "F6",
    "anti_afk_interval": 10,
    "admin_user_id": None  
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s', handlers=[
    logging.FileHandler(LOG_FILE, encoding='utf-8'),
    logging.StreamHandler(sys.stdout)
])

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f: cfg = json.load(f)
        updated = False
        for key, value in DEFAULT_CONFIG.items():
            if key not in cfg: cfg[key] = value; updated = True
        if updated: save_config(cfg)
        return cfg
    else:
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f: json.dump(cfg, f, indent=4, ensure_ascii=False)

config = load_config()
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

class TokenWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent); self.parent = parent; self.title("Введите Telegram токен")
        self.geometry("400x150"); self.resizable(False, False)
        ctk.CTkLabel(self, text="Введите токен Telegram бота:", font=("Arial", 14)).pack(pady=10, fill="x")
        self.token_entry = ctk.CTkEntry(self, width=360); self.token_entry.pack(pady=5, fill="x", padx=20)
        ctk.CTkButton(self, text="Сохранить", fg_color="#4a90e2", hover_color="#357ABD", command=self.save_token).pack(pady=10)

    def save_token(self):
        token = self.token_entry.get().strip()
        if not token: messagebox.showerror("Ошибка", "Токен не может быть пустым!"); return
        config["token"] = token; save_config(config); self.destroy()
        os.execl(sys.executable, sys.executable, *sys.argv)

class MinecraftPayApp(ctk.CTk):
    def __init__(self):
        super().__init__(); self.title("Автовыдача ВАЛЮТЫ BY VELENOK"); self.geometry("500x650")
        
        self.token = config["token"]
        self.delays = config["delays"]
        self.an_command = config.get("an_command", "/an605")
        self.esc_delay = config.get("esc_delay", 0.3)
        self.screenshot_delay = config.get("screenshot_delay", 2.0)
        self.anti_afk_enabled = config.get("anti_afk_enabled", False)
        self.anti_afk_hotkey = config.get("anti_afk_hotkey", "F6")
        self.anti_afk_interval = config.get("anti_afk_interval", 10)
        self.payment_in_progress = False
        self.anti_afk_thread = None
        self.bot_instance = None; self.main_loop = None

        self.create_widgets()
        if not self.token: self.after(500, self.ask_token)
        
        threading.Thread(target=self.hotkey_listener, daemon=True).start()
        if self.anti_afk_enabled: self.toggle_anti_afk()

    def ask_token(self): TokenWindow(self)

    def log_message(self, message, level='info'):
        if not hasattr(self, 'log_text') or not self.log_text.winfo_exists(): return
        self.log_text.configure(state="normal"); self.log_text.insert("end", message + "\n")
        self.log_text.see("end"); self.log_text.configure(state="disabled")
        if level == 'info': logging.info(message)
        elif level == 'error': logging.error(message)

    def toggle_theme(self):
        ctk.set_appearance_mode("Light" if ctk.get_appearance_mode() == "Dark" else "Dark")

    def create_widgets(self):
        theme_btn = ctk.CTkButton(self, text="Тема", width=50, fg_color="#4a90e2", hover_color="#357ABD", command=self.toggle_theme)
        theme_btn.pack(anchor="ne", padx=5, pady=5)
        self.header = ctk.CTkLabel(self, text="Celestial Автовыдача валюта FUNTIME", font=("Arial", 20, "bold"))
        self.header.pack(pady=10, fill="x")

        self.delay_frame = ctk.CTkFrame(self); self.delay_frame.pack(pady=10, fill="x", padx=20)
        labels = ["Перед началом:", "После команды /an:", "Перед /pay:"]
        self.delay_entries = []
        for i, label in enumerate(labels):
            ctk.CTkLabel(self.delay_frame, text=label).grid(row=i, column=0, padx=5, pady=3, sticky='w')
            entry = ctk.CTkEntry(self.delay_frame, width=100); entry.insert(0, str(self.delays[i] if i < len(self.delays) else DEFAULT_CONFIG["delays"][i]))
            entry.grid(row=i, column=1, padx=5, pady=3, sticky="ew"); self.delay_entries.append(entry)
        ctk.CTkLabel(self.delay_frame, text="Команда выдачи:").grid(row=3, column=0, padx=5, pady=3, sticky='w')
        self.an_command_entry = ctk.CTkEntry(self.delay_frame, width=100); self.an_command_entry.insert(0, self.an_command)
        self.an_command_entry.grid(row=3, column=1, padx=5, pady=3, sticky="ew")
        ctk.CTkLabel(self.delay_frame, text="Задержка между ESC (сек):").grid(row=4, column=0, padx=5, pady=3, sticky='w')
        self.esc_delay_entry = ctk.CTkEntry(self.delay_frame, width=100); self.esc_delay_entry.insert(0, str(self.esc_delay))
        self.esc_delay_entry.grid(row=4, column=1, padx=5, pady=3, sticky="ew")
        ctk.CTkLabel(self.delay_frame, text="Задержка для скриншота (сек):").grid(row=5, column=0, padx=5, pady=3, sticky='w')
        self.screenshot_delay_entry = ctk.CTkEntry(self.delay_frame, width=100); self.screenshot_delay_entry.insert(0, str(self.screenshot_delay))
        self.screenshot_delay_entry.grid(row=5, column=1, padx=5, pady=3, sticky="ew")

        self.afk_frame = ctk.CTkFrame(self); self.afk_frame.pack(pady=10, fill="x", padx=20)
        ctk.CTkLabel(self.afk_frame, text="Анти-АФК", font=("Arial", 14, "bold")).grid(row=0, column=0, columnspan=2, pady=5, sticky="w")
        self.anti_afk_var = ctk.BooleanVar(value=self.anti_afk_enabled)
        self.anti_afk_check = ctk.CTkCheckBox(self.afk_frame, text="Включить Анти-АФК", variable=self.anti_afk_var, command=self.toggle_anti_afk)
        self.anti_afk_check.grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky='w')
        ctk.CTkLabel(self.afk_frame, text="Горячая клавиша:").grid(row=2, column=0, padx=5, pady=3, sticky='w')
        self.anti_afk_hotkey_entry = ctk.CTkEntry(self.afk_frame, width=100); self.anti_afk_hotkey_entry.insert(0, self.anti_afk_hotkey)
        self.anti_afk_hotkey_entry.grid(row=2, column=1, padx=5, pady=3, sticky="ew")
        ctk.CTkLabel(self.afk_frame, text="Интервал (сек):").grid(row=3, column=0, padx=5, pady=3, sticky='w')
        self.anti_afk_interval_entry = ctk.CTkEntry(self.afk_frame, width=100); self.anti_afk_interval_entry.insert(0, str(self.anti_afk_interval))
        self.anti_afk_interval_entry.grid(row=3, column=1, padx=5, pady=3, sticky="ew")
        self.anti_afk_status_label = ctk.CTkLabel(self.afk_frame, text=f"Статус: {'ВКЛ' if self.anti_afk_enabled else 'ВЫКЛ'}", text_color="green" if self.anti_afk_enabled else "red")
        self.anti_afk_status_label.grid(row=4, column=0, columnspan=2, pady=5)

        save_btn = ctk.CTkButton(self, text="Сохранить настройки", fg_color="#4a90e2", hover_color="#357ABD", command=self.save_settings)
        save_btn.pack(pady=5, fill="x", padx=20)
        log_frame = ctk.CTkFrame(self); log_frame.pack(pady=10, fill="both", expand=True, padx=20)
        self.log_text = ctk.CTkTextbox(log_frame); self.log_text.pack(side="left", fill="both", expand=True); self.log_text.configure(state="disabled")
        scrollbar = ctk.CTkScrollbar(log_frame, command=self.log_text.yview); scrollbar.pack(side="right", fill="y"); self.log_text.configure(yscrollcommand=scrollbar.set)

    def save_settings(self):
        try:
            self.delays = [float(self.delay_entries[i].get()) for i in range(3)]
            self.an_command = self.an_command_entry.get()
            self.esc_delay = float(self.esc_delay_entry.get())
            self.screenshot_delay = float(self.screenshot_delay_entry.get())
            self.anti_afk_enabled = self.anti_afk_var.get()
            self.anti_afk_hotkey = self.anti_afk_hotkey_entry.get()
            self.anti_afk_interval = int(self.anti_afk_interval_entry.get())
        except (ValueError, IndexError): self.log_message("Некорректное значение в настройках.", "error"); return
        
        config.update({
            "delays": self.delays, "an_command": self.an_command, "esc_delay": self.esc_delay,
            "screenshot_delay": self.screenshot_delay, "anti_afk_enabled": self.anti_afk_enabled,
            "anti_afk_hotkey": self.anti_afk_hotkey, "anti_afk_interval": self.anti_afk_interval
        })
        save_config(config); self.log_message("Настройки сохранены.")

    def anti_afk_loop(self):
        while self.anti_afk_enabled:
            if not self.payment_in_progress:
                try:
                    self.log_message("Анти-АФК: Прыжок и поворот.")
                    if keyboard:
                        keyboard.press('space'); time.sleep(0.1); keyboard.release('space')
                        time.sleep(0.2)
                        turn_key = random.choice(['a', 'd'])
                        keyboard.press(turn_key); time.sleep(0.15); keyboard.release(turn_key)
                except Exception as e: self.log_message(f"Ошибка в цикле Анти-АФК: {e}", "error")
            
            for _ in range(self.anti_afk_interval):
                time.sleep(1)
                if not self.anti_afk_enabled: break

    def toggle_anti_afk(self):
        self.anti_afk_enabled = self.anti_afk_var.get()
        state_text, color = ("ВКЛ", "green") if self.anti_afk_enabled else ("ВЫКЛ", "red")
        self.log_message(f"Анти-АФК {state_text.lower()}.")
        self.anti_afk_status_label.configure(text=f"Статус: {state_text}", text_color=color)
        if self.anti_afk_enabled and (self.anti_afk_thread is None or not self.anti_afk_thread.is_alive()):
            self.anti_afk_thread = threading.Thread(target=self.anti_afk_loop, daemon=True)
            self.anti_afk_thread.start()

    def hotkey_listener(self):
        if not keyboard: return
        try: keyboard.remove_hotkey(self.anti_afk_hotkey)
        except (KeyError, AttributeError): pass
        keyboard.add_hotkey(self.anti_afk_hotkey, self.toggle_afk_from_hotkey)
        
    def toggle_afk_from_hotkey(self):
        self.anti_afk_var.set(not self.anti_afk_var.get())
        self.toggle_anti_afk()

    def parse_amount(self, amount):
        amount = amount.strip().upper()
        if amount.endswith("KK"): return int(float(amount[:-2]) * 1_000_000)
        return float(amount)
    
    def process_payment(self, player=None, amount=None, bot=None, chat_id=None, loop=None):
        self.payment_in_progress = True
        self.log_message("Анти-АФК приостановлен на время оплаты.")
        try:
            self.log_message("Начало выполнения команды /pay...")
            if not player or not amount: self.log_message("Ошибка: данные для оплаты не переданы!", "error"); return
            amount_val = self.parse_amount(amount)
            d1, d2, d3 = self.delays[:3]
            command_to_pay = f"/pay {player} {amount_val}"
            self.log_message(f"Команда: {command_to_pay}")
            time.sleep(d1)
            if keyboard is None: self.log_message("Модуль keyboard не установлен", "error"); return
            
            keyboard.press_and_release('esc'); time.sleep(self.esc_delay)
            keyboard.press_and_release('esc'); time.sleep(self.esc_delay)
            self.log_message(f"Ввожу команду {self.an_command}..."); time.sleep(1)
            keyboard.press_and_release('t'); time.sleep(0.5); keyboard.write(self.an_command); keyboard.press_and_release('enter'); time.sleep(d2)
            
            for i in range(2):
                self.log_message(f"Ввожу команду /pay... (попытка {i+1})")
                keyboard.press_and_release('t'); time.sleep(d3); keyboard.write(command_to_pay); keyboard.press_and_release('enter')
                if i == 1: self.log_message(f"Ожидаю {self.screenshot_delay} секунд для скриншота..."); time.sleep(self.screenshot_delay)
                else: time.sleep(0.5)
            
            if bot and chat_id and pyautogui:
                screenshot = pyautogui.screenshot(); bio = BytesIO(); bio.name = 'screenshot.jpg'; screenshot.save(bio, 'JPEG'); bio.seek(0)
                if loop: asyncio.run_coroutine_threadsafe(bot.send_photo(chat_id=chat_id, photo=bio), loop)
            
            self.log_message("Команда успешно отправлена!")
        except Exception as e: self.log_message(f"Критическая ошибка при отправке команды: {e}", "error")
        finally:
            self.log_message("Оплата завершена. Анти-АФК возобновится через 5 секунд.")
            time.sleep(5)
            self.payment_in_progress = False
            self.log_message("Анти-АФК возобновлен.")

    # --- Команды для Telegram-бота ---

    async def auth_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда для назначения администратора бота."""
        user_id = update.effective_user.id
        admin_id = config.get("admin_user_id")

        if admin_id is None:
            # Назначаем первого пользователя администратором
            config["admin_user_id"] = user_id
            save_config(config)
            self.log_message(f"Новый администратор назначен: {user_id}")
            await update.message.reply_text("✅ Вы успешно стали администратором этого бота. Теперь только вы можете им управлять.")
        elif admin_id == user_id:
            await update.message.reply_text("ℹ️ Вы уже являетесь администратором.")
        else:
            await update.message.reply_text("⛔️ У этого бота уже есть администратор.")

    async def pay_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
       
        admin_id = config.get("admin_user_id")
        if admin_id is None:
            await update.message.reply_text("⚠️ Бот не настроен. Пожалуйста, используйте команду /auth, чтобы стать администратором.")
            return
        if admin_id != update.effective_user.id:
            await update.message.reply_text("⛔️ У вас нет прав для выполнения этой команды.")
            return
        # ===========================

        if len(context.args) < 2: await update.message.reply_text("Используй: /pay <ник> <сумма>"); return
        player, amount = context.args[0], context.args[1]
        try: self.parse_amount(amount)
        except ValueError: await update.message.reply_text("Неверное число!"); return
        await update.message.reply_text(f"Отправка команды /pay {player} {amount}")
        loop = asyncio.get_running_loop()
        threading.Thread(target=self.process_payment, args=(player, amount, context.bot, update.effective_chat.id, loop), daemon=True).start()

    async def screenshot_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        admin_id = config.get("admin_user_id")
        if admin_id is None or admin_id != update.effective_user.id:
            await update.message.reply_text("⛔️ У вас нет прав для выполнения этой команды.")
            return

        if pyautogui is None: await update.message.reply_text("pyautogui не установлен"); return
        screenshot = pyautogui.screenshot(); bio = BytesIO(); bio.name = 'screenshot.jpg'; screenshot.save(bio, 'JPEG'); bio.seek(0)
        await update.message.reply_photo(bio)

    async def log_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        admin_id = config.get("admin_user_id")
        if admin_id is None or admin_id != update.effective_user.id:
            await update.message.reply_text("⛔️ У вас нет прав для выполнения этой команды.")
            return

        if os.path.exists(LOG_FILE):
            try:
                with open(LOG_FILE, "r", encoding="utf-8") as f: content = f.read()[-4000:]
                if content.strip(): await update.message.reply_text(f"```{content}```", parse_mode="MarkdownV2")
                else: await update.message.reply_text("Лог-файл пуст.")
            except Exception as e: await update.message.reply_text(f"Ошибка чтения лог-файла: {e}")
        else: await update.message.reply_text("Лог-файл не найден.")

def run_telegram_bot(app: MinecraftPayApp):
    loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
    app.main_loop = loop
    application = ApplicationBuilder().token(app.token).build()
    app.bot_instance = application.bot
    
   
    application.add_handler(CommandHandler("auth", app.auth_command))
    application.add_handler(CommandHandler("pay", app.pay_command))
    application.add_handler(CommandHandler("screenshot", app.screenshot_command))
    application.add_handler(CommandHandler("log", app.log_command))
    
    loop.run_until_complete(application.bot.set_my_commands([
        BotCommand("auth", "Стать администратором бота (только для первого пользователя)"),
        BotCommand("pay", "Отправить команду /pay <ник> <сумма>"),
        BotCommand("screenshot", "Сделать скриншот экрана"),
        BotCommand("log", "Получить лог программы")
    ]))
    
    application.run_polling()

if __name__ == "__main__":
    if not all([keyboard, pyautogui]):
        print("Внимание: одна или обе библиотеки (keyboard, pyautogui) не установлены.")
        print("Установите их для полной функциональности: pip install keyboard pyautogui")
    app = MinecraftPayApp()
    if app.token:
        bot_thread = threading.Thread(target=run_telegram_bot, args=(app,), daemon=True)
        bot_thread.start()

    app.mainloop()
