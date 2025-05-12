from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import json
from datetime import datetime
import time
import logging
import requests
import os

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('currency_parser.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    
    # В Docker/Render явно указываем путь к chromedriver
    service = Service('/usr/local/bin/chromedriver')
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def send_to_make(json_filename, webhook_url):
    try:
        with open(json_filename, 'r', encoding='utf-8') as f:
            data = f.read()
        headers = {'Content-Type': 'application/json'}
        response = requests.post(webhook_url, data=data, headers=headers)
        logging.info(f'Статус отправки в Make: {response.status_code}')
        return response.status_code == 200
    except Exception as e:
        logging.error(f'Ошибка при отправке в Make: {e}')
        return False

def get_currency_rates():
    driver = setup_driver()
    try:
        logging.info("Начинаем парсинг курсов валют")
        url = "https://www.mercantile.co.il/private/foregin-currency/exchange-rates/"
        driver.get(url)
        
        # Ждем загрузки страницы
        time.sleep(10)
        
        # Получаем HTML
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        
        # Находим таблицу с курсами
        table = soup.find('table')
        if not table:
            logging.error("Таблица с курсами не найдена")
            return None
            
        # Находим все строки с курсами валют
        rates = []
        rows = table.find_all('tr')[1:]  # Пропускаем заголовок
        
        for row in rows:
            try:
                # Извлекаем данные из каждой строки
                cells = row.find_all('td')
                if len(cells) >= 4:
                    currency_code = cells[0].text.strip()
                    currency_name = cells[1].text.strip()
                    buy_rate = cells[2].text.strip().replace(',', '')
                    sell_rate = cells[3].text.strip().replace(',', '')
                    
                    rate_data = {
                        "currency_code": currency_code,
                        "currency_name": currency_name,
                        "buy_rate": float(buy_rate) if buy_rate else None,
                        "sell_rate": float(sell_rate) if sell_rate else None,
                        "timestamp": datetime.now().isoformat()
                    }
                    rates.append(rate_data)
                    logging.info(f"Обработана валюта: {currency_code}")
                
            except Exception as e:
                logging.error(f"Ошибка при обработке строки: {e}")
                continue
        
        # Создаем структуру данных
        data = {
            "timestamp": datetime.now().isoformat(),
            "source": "Mercantile Bank",
            "rates": rates
        }
        
        # Сохраняем в JSON
        filename = f"currency_rates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        logging.info(f"Данные успешно сохранены в файл {filename}")

        # Отправляем в Make
        webhook_url = os.getenv('MAKE_WEBHOOK_URL')
        if webhook_url:
            if send_to_make(filename, webhook_url):
                logging.info("Данные успешно отправлены в Make")
            else:
                logging.error("Не удалось отправить данные в Make")
        else:
            logging.warning("URL для Make не настроен")

        return filename
        
    except Exception as e:
        logging.error(f"Произошла ошибка при парсинге: {e}")
        raise
    finally:
        driver.quit()

if __name__ == "__main__":
    try:
        get_currency_rates()
    except Exception as e:
        logging.error(f"Критическая ошибка: {e}")
        exit(1) 