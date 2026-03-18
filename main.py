"""
MS Fetcher Mobile – Main App
"""

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.lang import Builder
from kivy.properties import StringProperty, NumericProperty, BooleanProperty
from kivy.clock import Clock
from kivy.uix.popup import Popup
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
import threading
import queue
import os
import json

# Import checker functions (from fetcher.py)
from fetcher import *

# Load UI files
Builder.load_file('main.kv')
Builder.load_file('checker.kv')
Builder.load_file('settings.kv')
Builder.load_file('promo.kv')  # we'll create a separate screen for promo puller later

# Queue for log messages from background thread to UI
log_queue = queue.Queue()

class MainScreen(Screen):
    pass

class ComboScreen(Screen):
    combo_path = StringProperty('')
    combo_content = StringProperty('')

    def load_file(self):
        content = BoxLayout(orientation='vertical')
        filechooser = FileChooserListView(path=os.getcwd())
        content.add_widget(filechooser)
        btn_layout = BoxLayout(size_hint_y=0.1)
        btn_layout.add_widget(Button(text='Cancel', on_release=lambda x: self.dismiss_popup()))
        btn_layout.add_widget(Button(text='Select', on_release=lambda x: self.select_file(filechooser.path, filechooser.selection)))
        content.add_widget(btn_layout)
        self.popup = Popup(title='Choose Combo File', content=content, size_hint=(0.9,0.9))
        self.popup.open()

    def dismiss_popup(self):
        self.popup.dismiss()

    def select_file(self, path, selection):
        if selection:
            self.combo_path = selection[0]
            with open(self.combo_path, 'r', encoding='utf-8', errors='ignore') as f:
                self.combo_content = f.read()
        self.popup.dismiss()

    def start_checker(self):
        app = App.get_running_app()
        app.checker_screen.combo_content = self.combo_content
        app.root.current = 'checker'
        Clock.schedule_once(lambda dt: app.checker_screen.start_check(), 0.1)

class CheckerScreen(Screen):
    hits = NumericProperty(0)
    valid = NumericProperty(0)
    dead = NumericProperty(0)
    errors = NumericProperty(0)
    checked = NumericProperty(0)
    cpm = NumericProperty(0)
    log_text = StringProperty('')
    running = False
    combo_content = ''

    def start_check(self):
        if not self.combo_content.strip():
            self.log_text = "No combos loaded."
            return
        self.running = True
        self.hits = 0
        self.valid = 0
        self.dead = 0
        self.errors = 0
        self.checked = 0
        self.log_text = ''
        while not log_queue.empty():
            log_queue.get()
        self.thread = threading.Thread(target=self.run_checker)
        self.thread.daemon = True
        self.thread.start()
        Clock.schedule_interval(self.update_ui, 0.5)

    def run_checker(self):
        combos = [line.strip() for line in self.combo_content.split('\n') if ':' in line]
        proxies = load_proxies_from_settings()
        for combo in combos:
            if not self.running:
                break
            check_microsoft_account(combo, proxies)  # all features enabled inside fetcher.py

    def stop_check(self):
        self.running = False

    def update_ui(self, dt):
        from fetcher import ms_hits, ms_valid, ms_dead, ms_errors, ms_checked_count, ms_start_time
        self.hits = len(ms_hits)
        self.valid = len(ms_valid)
        self.dead = len(ms_dead)
        self.errors = len(ms_errors)
        self.checked = ms_checked_count
        if ms_checked_count > 0:
            elapsed = time.time() - ms_start_time
            if elapsed > 0:
                self.cpm = ms_checked_count / elapsed * 60
        while not log_queue.empty():
            self.log_text += log_queue.get() + '\n'
        if not self.thread.is_alive():
            Clock.unschedule(self.update_ui)

    def go_results(self):
        App.get_running_app().root.current = 'results'

class ResultsScreen(Screen):
    results_list = StringProperty('')
    def on_enter(self):
        from fetcher import ms_hits, ms_valid, ms_dead
        text = ''
        for hit in ms_hits:
            text += f'✅ HIT: {hit}\n'
        for val in ms_valid:
            text += f'✔️ VALID: {val}\n'
        for dead in ms_dead:
            text += f'❌ DEAD: {dead}\n'
        self.results_list = text

    def export(self):
        from kivy.utils import platform
        if platform == 'android':
            from android.storage import primary_external_storage_path
            path = primary_external_storage_path()
        else:
            path = os.getcwd()
        filename = os.path.join(path, 'MSFetcher_results.txt')
        with open(filename, 'w') as f:
            f.write(self.results_list)
        self.results_list += f"\n\nResults saved to {filename}"

class SettingsScreen(Screen):
    proxy_info = StringProperty('')
    threads = NumericProperty(25)
    minecraft = BooleanProperty(True)
    full_capture = BooleanProperty(True)
    hypixel = BooleanProperty(False)
    promo = BooleanProperty(True)
    # Webhook URLs
    webhook_mc = StringProperty('')
    webhook_promo = StringProperty('')
    webhook_code = StringProperty('')
    webhook_paypal = StringProperty('')
    webhook_cc = StringProperty('')
    webhook_subs = StringProperty('')
    webhook_rewards = StringProperty('')

    def on_enter(self):
        from fetcher import SETTINGS
        self.threads = SETTINGS.get('checker_threads', 25)
        self.minecraft = SETTINGS.get('enable_minecraft', True)
        self.full_capture = SETTINGS.get('enable_full_capture', True)
        self.hypixel = SETTINGS.get('enable_hypixel', False)
        self.promo = SETTINGS.get('enable_promo', True)
        webhooks = SETTINGS.get('webhooks', {})
        self.webhook_mc = webhooks.get('minecraft', '')
        self.webhook_promo = webhooks.get('promo', '')
        self.webhook_code = webhooks.get('code', '')
        self.webhook_paypal = webhooks.get('paypal', '')
        self.webhook_cc = webhooks.get('cc', '')
        self.webhook_subs = webhooks.get('subscriptions', '')
        self.webhook_rewards = webhooks.get('rewards', '')
        proxies = SETTINGS.get('proxy')
        if proxies:
            if isinstance(proxies, list):
                self.proxy_info = f"{len(proxies)} proxies loaded"
            else:
                self.proxy_info = proxies
        else:
            self.proxy_info = "No proxies"

    def save(self):
        from fetcher import SETTINGS, save_settings
        SETTINGS['checker_threads'] = int(self.threads)
        SETTINGS['enable_minecraft'] = self.minecraft
        SETTINGS['enable_full_capture'] = self.full_capture
        SETTINGS['enable_hypixel'] = self.hypixel
        SETTINGS['enable_promo'] = self.promo
        webhooks = {
            'minecraft': self.webhook_mc,
            'promo': self.webhook_promo,
            'code': self.webhook_code,
            'paypal': self.webhook_paypal,
            'cc': self.webhook_cc,
            'subscriptions': self.webhook_subs,
            'rewards': self.webhook_rewards
        }
        SETTINGS['webhooks'] = webhooks
        save_settings()

class PromoScreen(Screen):
    # Placeholder for future expansion – you can add a standalone promo puller
    pass

class MSFetcherApp(App):
    def build(self):
        sm = ScreenManager()
        sm.add_widget(MainScreen(name='main'))
        sm.add_widget(ComboScreen(name='combo'))
        sm.add_widget(CheckerScreen(name='checker'))
        sm.add_widget(ResultsScreen(name='results'))
        sm.add_widget(SettingsScreen(name='settings'))
        sm.add_widget(PromoScreen(name='promo'))
        self.checker_screen = sm.get_screen('checker')
        return sm

if __name__ == '__main__':
    MSFetcherApp().run()