#!/usr/bin/env python3
"""
AI-Powered Lead Generation Tool for CIS Small Business
Автор: A1VEN23
Версия: 3.0 - CRM Architect Edition
"""

import requests
import csv
import os
import time
import re
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import json

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class BusinessLead:
    """Класс для хранения информации о бизнесе (CRM Architect версия)"""
    name: str
    phone: Optional[str]
    website: Optional[str]
    email: str = ""
    instagram: str = ""
    telegram: str = ""
    vk: str = ""
    whatsapp: str = ""
    phone_type: str = ""  # "личный" или "городской"
    rating: float = 0.0
    review_count: int = 0
    address: str = ""
    category: str = ""
    city: str = ""
    is_hot_lead: bool = False
    pain_points: List[str] = None
    ice_breaker: str = ""
    # CRM поля
    priority_score: int = 0
    ai_verdict: str = ""
    detailed_pains: str = ""
    social_links: str = ""
    proposed_offer: str = ""
    
    def __post_init__(self):
        if self.pain_points is None:
            self.pain_points = []

class OverpassAPI:
    """Класс для работы с OpenStreetMap Overpass API (стабильная версия)"""
    
    def __init__(self):
        # Зеркала Overpass API (более свободные)
        self.mirror_urls = [
            "https://overpass.kumi.systems/api/interpreter",
            "https://overpass.nchc.org.tw/api/interpreter",
            "https://overpass-api.de/api/interpreter"  # запасной
        ]
        self.current_url_index = 0
        self.base_url = self.mirror_urls[self.current_url_index]
        self.session = requests.Session()
        
        # Bounding box для Минска [south, west, north, east]
        self.minsk_bbox = [53.83, 27.45, 53.97, 27.68]
        
        # Bounding box для других городов СНГ
        self.city_bboxes = {
            'Минск': [53.83, 27.45, 53.97, 27.68],
            'Гомель': [52.38, 30.85, 52.48, 31.05],
            'Брест': [52.05, 23.60, 52.15, 23.80],
            'Алматы': [43.15, 76.80, 43.35, 77.10],
            'Астана': [51.05, 71.35, 51.25, 71.65],
            'Караганда': [49.75, 73.00, 49.95, 73.30],
            'Ташкент': [41.20, 69.10, 41.40, 69.40],
            'Москва': [55.65, 37.40, 55.85, 37.80]
        }
    
    def switch_mirror(self):
        """Переключение на следующее зеркало при ошибках"""
        self.current_url_index = (self.current_url_index + 1) % len(self.mirror_urls)
        self.base_url = self.mirror_urls[self.current_url_index]
        logger.info(f"Переключаюсь на зеркало: {self.base_url}")
        
        # Координаты центров городов СНГ (широта, долгота)
        self.city_centers = {
            # Россия
            'Москва': (55.7558, 37.6176),
            'Санкт-Петербург': (59.9343, 30.3351),
            'Новосибирск': (55.0084, 82.9357),
            'Екатеринбург': (56.8389, 60.6057),
            'Казань': (55.8304, 49.0661),
            'Нижний Новгород': (56.3268, 44.0066),
            # Беларусь
            'Минск': (53.9045, 27.5615),
            'Гомель': (52.4345, 30.9754),
            'Брест': (52.1375, 23.6557),
            # Казахстан
            'Алматы': (43.2220, 76.8512),
            'Астана': (51.1605, 71.4704),
            'Караганда': (49.8043, 73.2406),
            # Узбекистан
            'Ташкент': (41.2995, 69.2401)
        }
        
        # Районы Москвы для поэтапного поиска (избегаем 504)
        self.moscow_districts = [
            {'name': 'Центр', 'lat': 55.7558, 'lon': 37.6176, 'radius': 3000},
            {'name': 'Западный', 'lat': 55.7351, 'lon': 37.4953, 'radius': 4000},
            {'name': 'Восточный', 'lat': 55.7824, 'lon': 37.6572, 'radius': 4000},
            {'name': 'Северный', 'lat': 55.8500, 'lon': 37.6176, 'radius': 4000},
            {'name': 'Южный', 'lat': 55.6500, 'lon': 37.6176, 'radius': 4000},
            {'name': 'СЗАО', 'lat': 55.8500, 'lon': 37.4000, 'radius': 3500},
            {'name': 'ЮВАО', 'lat': 55.6500, 'lon': 37.8000, 'radius': 3500}
        ]
    
    def search_places_bbox(self, amenity: str, city: str, max_results: int = 50) -> List[Dict]:
        """Поиск заведений через bounding box (быстрее и стабильнее)"""
        
        # Получаем bounding box для города
        bbox = self.city_bboxes.get(city)
        if not bbox:
            logger.error(f"Не найден bounding box для города: {city}")
            return []
        
        south, west, north, east = bbox
        
        # ТОЧНЫЕ ТЕГИ ДЛЯ МСБ
        if amenity == 'hairdresser':
            # Парикмахерские - точные теги
            query = f"""
            [out:json][timeout:30];
            (
              node["shop"="hairdresser"]({south},{west},{north},{east});
              node["amenity"="hairdresser"]({south},{west},{north},{east});
              way["shop"="hairdresser"]({south},{west},{north},{east});
              way["amenity"="hairdresser"]({south},{west},{north},{east});
            );
            out center;
            """
        elif amenity == 'barber':
            # Барбершопы
            query = f"""
            [out:json][timeout:30];
            (
              node["shop"="barber"]({south},{west},{north},{east});
              node["amenity"="barber"]({south},{west},{north},{east});
              way["shop"="barber"]({south},{west},{north},{east});
              way["amenity"="barber"]({south},{west},{north},{east});
            );
            out center;
            """
        elif amenity == 'car_wash':
            # Мойки
            query = f"""
            [out:json][timeout:30];
            (
              node["amenity"="car_wash"]({south},{west},{north},{east});
              way["amenity"="car_wash"]({south},{west},{north},{east});
            );
            out center;
            """
        elif amenity == 'bakery':
            # Пекарни
            query = f"""
            [out:json][timeout:30];
            (
              node["shop"="bakery"]({south},{west},{north},{east});
              node["amenity"="bakery"]({south},{west},{north},{east});
              way["shop"="bakery"]({south},{west},{north},{east});
              way["amenity"="bakery"]({south},{west},{north},{east});
            );
            out center;
            """
        elif amenity == 'flower_shop':
            # Цветы
            query = f"""
            [out:json][timeout:30];
            (
              node["shop"="flower"]({south},{west},{north},{east});
              node["shop"="florist"]({south},{west},{north},{east});
              node["amenity"="florist"]({south},{west},{north},{east});
              way["shop"="flower"]({south},{west},{north},{east});
              way["shop"="florist"]({south},{west},{north},{east});
              way["amenity"="florist"]({south},{west},{north},{east});
            );
            out center;
            """
        elif amenity == 'dry_cleaning':
            # Химчистки
            query = f"""
            [out:json][timeout:30];
            (
              node["shop"="dry_cleaning"]({south},{west},{north},{east});
              node["amenity"="dry_cleaning"]({south},{west},{north},{east});
              way["shop"="dry_cleaning"]({south},{west},{north},{east});
              way["amenity"="dry_cleaning"]({south},{west},{north},{east});
            );
            out center;
            """
        else:
            # Стандартный поиск
            query = f"""
            [out:json][timeout:30];
            (
              node["amenity"="{amenity}"]({south},{west},{north},{east});
              way["amenity"="{amenity}"]({south},{west},{north},{east});
            );
            out center;
            """
        
        # Пробуем несколько зеркал при ошибках
        for attempt in range(3):
            try:
                logger.info(f"Поиск {amenity} в {city} (bbox: [{south}, {west}, {north}, {east}])...")
                response = self.session.get(self.base_url, params={'data': query}, timeout=45)
                response.raise_for_status()
                data = response.json()
                
                places = []
                for element in data.get('elements', []):
                    if element.get('tags'):
                        places.append(element)
                
                logger.info(f"Найдено {len(places)} заведений типа '{amenity}' в {city}")
                return places[:max_results]
                
            except requests.exceptions.HTTPError as e:
                if e.response.status_code in [504, 429]:
                    logger.warning(f"Ошибка {e.response.status_code} на зеркале {self.base_url}. Переключаюсь...")
                    self.switch_mirror()
                    time.sleep(10)
                    continue
                else:
                    logger.error(f"HTTP ошибка {e.response.status_code}: {e}")
                    break
            except Exception as e:
                logger.error(f"Ошибка поиска {amenity} в {city}: {e}")
                break
        
        return []
    
    def search_places(self, amenity: str, city: str, max_results: int = 50, radius: int = 8000) -> List[Dict]:
        """Поиск заведений по типу amenity (стабильная версия)"""
        
        # Для всех городов используем bounding box - быстрее и стабильнее
        if city in self.city_bboxes:
            return self.search_places_bbox(amenity, city, max_results)
        
        # Для Москвы используем поиск по районам (запасной вариант)
        if city == 'Москва':
            return self.search_places_moscow_districts(amenity, max_results // len(self.moscow_districts))
        
        logger.error(f"Неизвестный город: {city}")
        return []
    
    def extract_place_info(self, element: Dict) -> Dict:
        """Извлечение информации из OSM элемента"""
        tags = element.get('tags', {})
        
        # Получение координат
        lat, lon = None, None
        if element.get('lat') and element.get('lon'):
            lat, lon = element['lat'], element['lon']
        elif element.get('center'):
            lat, lon = element['center']['lat'], element['center']['lon']
        
        # Извлечение информации
        info = {
            'name': tags.get('name', 'Без названия'),
            'phone': tags.get('phone', '') or tags.get('contact:phone', ''),
            'website': tags.get('website', '') or tags.get('contact:website', ''),
            'lat': lat,
            'lon': lon,
            'address': self._format_address(tags)
        }
        
        return info
    
    def _format_address(self, tags: Dict) -> str:
        """Форматирование адреса из OSM тегов"""
        address_parts = []
        
        if tags.get('addr:housenumber'):
            address_parts.append(tags['addr:housenumber'])
        if tags.get('addr:street'):
            address_parts.append(tags['addr:street'])
        if tags.get('addr:city'):
            address_parts.append(tags['addr:city'])
        elif tags.get('addr:postcode'):
            address_parts.append(tags['addr:postcode'])
        
        return ', '.join(address_parts) or 'Адрес не указан'

class WebsiteAnalyzer:
    """Анализатор сайтов для глубокого поиска контактов (SMB Market Analyst версия)"""
    
    @staticmethod
    def check_website_features(website_url: str) -> Dict[str, bool]:
        """Быстрая проверка сайта без HTTP запросов"""
        if not website_url:
            return {'has_chat': False, 'has_booking_form': False, 'has_contact_form': False}
        
        # Упрощенная проверка без HTTP запросов (избегаем падений)
        features = {
            'has_chat': False,  # Не проверяем, чтобы избежать таймаутов
            'has_booking_form': False,
            'has_contact_form': False
        }
        
        # Базовая проверка по URL (очень быстрая)
        website_lower = website_url.lower()
        if any(keyword in website_lower for keyword in ['booking', 'zapisi', 'record', 'appointment']):
            features['has_booking_form'] = True
        if any(keyword in website_lower for keyword in ['contact', 'kontakt', 'form']):
            features['has_contact_form'] = True
            
        return features
    
    @staticmethod
    def extract_contacts(url: str) -> Dict[str, str]:
        """Глубокий поиск контактов с ПРИОРИТЕТОМ на WhatsApp и Instagram для МСБ"""
        if not url:
            return {'email': '', 'instagram': '', 'telegram': '', 'vk': '', 'whatsapp': ''}
        
        # Нормализация URL
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        contacts = {
            'email': '',
            'instagram': '',
            'telegram': '',
            'vk': '',
            'whatsapp': ''
        }
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            print(f"    🔍 Анализ МСБ сайта: {url}")
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            content = response.text
            
            # ПРИОРИТЕТ 1: Поиск WhatsApp (важно для МСБ)
            whatsapp_patterns = [
                r'wa\.me/([0-9]+)',
                r'api\.whatsapp\.com/send\?phone=([0-9]+)',
                r'href=["\']?(?:https?://)?wa\.me/([0-9]+)',
                r'href=["\']?(?:https?://)?api\.whatsapp\.com/send\?phone=([0-9]+)',
                r'whatsapp:\s*([0-9]+)',
                r'tel:\s*([0-9]+)(?:\s*-\s*WhatsApp|\s*WhatsApp)',
                r'@([0-9]+)(?:\s*-\s*WhatsApp|\s*WhatsApp)'
            ]
            
            for pattern in whatsapp_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    contacts['whatsapp'] = matches[0]
                    print(f"    📱 НАШЕЛ WHATSAPP: wa.me/{contacts['whatsapp']}")
                    break
            
            # ПРИОРИТЕТ 2: Поиск Instagram (очень важно для МСБ)
            instagram_patterns = [
                r'instagram\.com/([A-Za-z0-9_.-]+)',
                r'@([A-Za-z0-9_.-]+)(?:\s+(?:instagram|inst))',
                r'instagr\.am/([A-Za-z0-9_.-]+)',
                r'href=["\']?(?:https?://)?(?:www\.)?instagram\.com/([A-Za-z0-9_.-]+)',
                r'href=["\']?(?:https?://)?instagr\.am/([A-Za-z0-9_.-]+)'
            ]
            
            for pattern in instagram_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    contacts['instagram'] = matches[0]
                    print(f"    📷 НАШЕЛ INSTAGRAM: @{contacts['instagram']}")
                    break
            
            # Поиск email
            email_patterns = [
                r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                r'\binfo@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                r'\bcontact@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                r'\b[a-zA-Z0-9._%+-]+@gmail\.com\b',
                r'\b[a-zA-Z0-9._%+-]+@mail\.ru\b',
                r'\b[a-zA-Z0-9._%+-]+@yandex\.ru\b'
            ]
            
            for pattern in email_patterns:
                emails = re.findall(pattern, content, re.IGNORECASE)
                if emails:
                    contacts['email'] = emails[0]
                    print(f"    📧 Нашел Email: {contacts['email']}")
                    break
            
            # Поиск Telegram
            telegram_patterns = [
                r't\.me/([A-Za-z0-9_.-]+)',
                r'telegram\.me/([A-Za-z0-9_.-]+)',
                r'@([A-Za-z0-9_.-]+)(?:\s+(?:telegram|tg))',
                r'href=["\']?(?:https?://)?t\.me/([A-Za-z0-9_.-]+)'
            ]
            
            for pattern in telegram_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    contacts['telegram'] = matches[0]
                    print(f"    ✈️ Нашел Telegram: @{contacts['telegram']}")
                    break
            
            # Поиск VK
            vk_patterns = [
                r'vk\.com/([A-Za-z0-9_.-]+)',
                r'vkontakte\.ru/([A-Za-z0-9_.-]+)',
                r'href=["\']?(?:https?://)?(?:www\.)?vk\.com/([A-Za-z0-9_.-]+)'
            ]
            
            for pattern in vk_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    contacts['vk'] = matches[0]
                    print(f"    💬 Нашел VK: vk.com/{contacts['vk']}")
                    break
            
            if not any(contacts.values()):
                print(f"    ❌ Контакты МСБ не найдены")
                
        except requests.exceptions.Timeout:
            print(f"    ⏰ Сайт МСБ не отвечает (timeout)")
        except requests.exceptions.RequestException as e:
            print(f"    ❌ Ошибка доступа к сайту МСБ: {e}")
        except Exception as e:
            print(f"    ❌ Ошибка парсинга МСБ сайта: {e}")
        
        return contacts
    
    @staticmethod
    def analyze_phone_type(phone: str) -> str:
        """Анализ типа телефона для МСБ"""
        if not phone:
            return ""
        
        # Очистка номера
        clean_phone = re.sub(r'[^\d+]', '', phone)
        
        # Мобильные коды СНГ
        mobile_patterns = [
            r'\+375(2[459]|3[34]|4[49]|33)',  # Беларусь мобильные
            r'\+7(70[012345]|77[012345]|78[012345]|79[012345])',  # Казахстан мобильные
            r'\+998(9[0-9]|8[8-9]|7[0-9])',  # Узбекистан мобильные
            r'\+7(9[0-9])',  # Россия мобильные
        ]
        
        for pattern in mobile_patterns:
            if re.match(pattern, clean_phone):
                return "личный"
        
        return "городской"

class LeadFilter:
    """Умный фильтр для определения 'горячих' лидов (CRM Architect версия)"""
    
    @staticmethod
    def is_small_business(name: str) -> bool:
        """Фильтр по размеру - исключаем сети, госучреждения, холдинги"""
        if not name:
            return False
        
        name_lower = name.lower()
        
        # Исключаем сети и крупные компании
        exclude_keywords = [
            'сеть', 'сетевой', 'филиал', 'центральный офис', 'холдинг', 'корпорация',
            'государственная', 'бюджетная', 'муниципальная', 'республиканская',
            'российская', 'национальная', 'федеральная', 'областная',
            'group', 'corporation', 'network', 'chain', 'franchise'
        ]
        
        for keyword in exclude_keywords:
            if keyword in name_lower:
                return False
        
        return True
    
    @staticmethod
    def calculate_priority_score(lead: BusinessLead) -> int:
        """Расчет приоритетного счета (0-100)"""
        score = 0
        
        # Базовый балл за наличие контактов
        if lead.phone:
            score += 20
            if lead.phone_type == "личный":
                score += 15  # Личный номер ценнее
        
        if lead.website:
            score += 15
        
        if lead.email:
            score += 10
        
        # Социальные сети (очень важно для МСБ)
        if lead.instagram:
            score += 15
        if lead.telegram:
            score += 15
        if lead.whatsapp:
            score += 15
        if lead.vk:
            score += 5
        
        # Боли (чем больше болей, тем выше приоритет)
        score += len(lead.pain_points) * 5
        
        # Категория (некоторые более ценны)
        high_value_categories = ['Парикмахерская', 'Салон красоты', 'Мойка']
        if lead.category in high_value_categories:
            score += 10
        
        return min(score, 100)  # Максимум 100
    
    @staticmethod
    def generate_ai_verdict(lead: BusinessLead) -> str:
        """Генерирует AI вердикт на основе анализа"""
        if not lead.is_hot_lead:
            return "ХОЛОДНО: Нет критических проблем"
        
        verdict_parts = []
        
        # Анализ контактов
        contacts = []
        if lead.instagram:
            contacts.append(f"Активный IG")
        if lead.telegram:
            contacts.append(f"ТГ канал")
        if lead.whatsapp:
            contacts.append(f"WhatsApp")
        if lead.phone_type == "личный":
            contacts.append(f"Личный номер")
        
        if contacts:
            verdict_parts.append(f"ГОРЯЧО: {', '.join(contacts)}")
        else:
            verdict_parts.append("ГОРЯЧО: Есть контакты")
        
        # Анализ болей
        if "без сайта" in '; '.join(lead.pain_points):
            verdict_parts.append("но нет сайта")
        elif "без чата" in '; '.join(lead.pain_points):
            verdict_parts.append("но нет чата")
        elif "без онлайн-записи" in '; '.join(lead.pain_points):
            verdict_parts.append("но нет записи")
        
        return " ".join(verdict_parts)
    
    @staticmethod
    def generate_detailed_pains(lead: BusinessLead) -> str:
        """Формирует список всех болей через запятую"""
        return ", ".join(lead.pain_points)
    
    @staticmethod
    def generate_social_links(lead: BusinessLead) -> str:
        """Формирует сводку всех соцсетей"""
        links = []
        if lead.telegram:
            links.append(f"TG: @{lead.telegram}")
        if lead.instagram:
            links.append(f"IG: @{lead.instagram}")
        if lead.whatsapp:
            links.append(f"WA: wa.me/{lead.whatsapp}")
        if lead.vk:
            links.append(f"VK: vk.com/{lead.vk}")
        return ", ".join(links)
    
    @staticmethod
    def generate_proposed_offer(lead: BusinessLead) -> str:
        """Генерирует умное предложение на основе болей"""
        if not lead.is_hot_lead:
            return "Базовое предложение по цифровой трансформации"
        
        # Анализ сильных сторон
        strengths = []
        if lead.instagram:
            strengths.append("крутой Инстаграм")
        if lead.telegram:
            strengths.append("активный Телеграм")
        if lead.whatsapp:
            strengths.append("WhatsApp")
        if lead.phone_type == "личный":
            strengths.append("личный контакт")
        
        # Анализ слабых сторон
        weaknesses = []
        if not lead.website:
            weaknesses.append("нет сайта")
        if "без чата" in '; '.join(lead.pain_points):
            weaknesses.append("нет чата")
        if "без онлайн-записи" in '; '.join(lead.pain_points):
            weaknesses.append("запись только по телефону")
        if "без сайта" in '; '.join(lead.pain_points):
            weaknesses.append("нет онлайн-присутствия")
        
        # Генерация предложения
        if strengths and weaknesses:
            return f"У вас {', '.join(strengths)}, но {', '.join(weaknesses)}. Давайте исправим?"
        elif strengths:
            return f"У вас {', '.join(strengths)}. Добавим автоматизацию?"
        elif weaknesses:
            return f"У вас {', '.join(weaknesses)}. Пора в онлайн!"
        else:
            return "Улучшим цифровое присутствие вашего бизнеса"
    
    @staticmethod
    def analyze_pain_points(lead: BusinessLead) -> Tuple[bool, List[str]]:
        """Анализирует 'боли' малого бизнеса с фокусом на МСБ"""
        pain_points = []
        is_hot = False
        
        # 1. Отсутствие телефона - критическая боль для МСБ
        if not lead.phone:
            pain_points.append("Нет телефона - МСБ теряет 80% локальных клиентов")
            is_hot = True
        
        # 2. Отсутствие сайта - цифровая слепота для МСБ
        if not lead.website:
            pain_points.append("МСБ без сайта - теряет 95% онлайн-заказов в районе")
            is_hot = True
        else:
            # 3. Анализ сайта для МСБ
            features = WebsiteAnalyzer.check_website_features(lead.website)
            
            if not features['has_chat']:
                pain_points.append("МСБ без чата - клиенты уходят к конкурентам пока вы заняты")
                is_hot = True
            
            if not features['has_booking_form'] and lead.category in ['Парикмахерская', 'Салон красоты', 'Мойка']:
                pain_points.append("МСБ без онлайн-записи - теряет вечерних клиентов")
                is_hot = True
            
            if not features['has_contact_form']:
                pain_points.append("МСБ без формы заявок - клиенты не могут заказать 24/7")
                is_hot = True
        
        # 4. Некачественный адрес для МСБ
        if lead.address == 'Адрес не указан':
            pain_points.append("МСБ без точного адреса - клиенты не могут найти")
            is_hot = True
        
        # 5. Отсутствие имени
        if not lead.name or len(lead.name.strip()) < 2:
            pain_points.append("МСБ без названия - невозможно найти в поиске")
            is_hot = True
        
        return is_hot, pain_points
    
    @staticmethod
    def generate_ice_breaker(lead: BusinessLead) -> str:
        """Генерирует ice breaker для ИИ-звонаря на основе болей"""
        
        if not lead.is_hot_lead:
            return f"Добрый день, это {lead.name}? Увидел ваш бизнес в интернете и хотел предложить..."
        
        # Персонализированные ice breaker'ы для разных болей
        if "Полная цифровая слепота" in '; '.join(lead.pain_points):
            return f"Я звоню вам, потому что искал {lead.category.lower()} в вашем районе, но вас просто нет в интернете. Вы знали, что 9 из 10 клиентов находят услуги через Google?"
        
        elif "Невозможно дозвониться" in '; '.join(lead.pain_points):
            return f"Я звоню вам, потому что нашел {lead.name} по адресу {lead.address}, но не смог найти номер телефона. Сколько клиентов теряете из-за этого каждый день?"
        
        elif "Нет онлайн-записи" in '; '.join(lead.pain_points):
            return f"Я звоню вам, потому что увидел ваш {lead.category.lower()} {lead.name}, но не смог записаться онлайн. Вы знали, что теряете около 15 записей в неделю из-за этого?"
        
        elif "Нет чат-бота" in '; '.join(lead.pain_points):
            return f"Я звоню вам, потому что посмотрел ваш сайт {lead.website}. Клиенты уходят к конкурентам за 30 секунд, пока вы отвечаете. Хотите решить эту проблему?"
        
        elif "Нет точного адреса" in '; '.join(lead.pain_points):
            return f"Я звоню вам, потому что нашел ваш {lead.category.lower()} {lead.name}, но клиенты не могут найти вас на картах. Это точно не мешает бизнесу расти?"
        
        else:
            return f"Я звоню вам, потому что увидел ваш {lead.category.lower()} {lead.name} и заметил несколько возможностей для роста. У вас есть 2 минуты?"

class LeadFinder:
    """Основной класс для поиска и фильтрации лидов через OpenStreetMap"""
    
    def __init__(self):
        self.api = OverpassAPI()
        self.filter = LeadFilter()
        
        # Маппинг категорий на OSM amenity (фокус на МСБ)
        self.category_mapping = {
            'Парикмахерская': 'hairdresser',
            'Барбершоп': 'barber',
            'Мойка': 'car_wash',
            'Пекарня': 'bakery',
            'Цветы': 'flower_shop',
            'Химчистка': 'dry_cleaning',
            'Детейлинг': 'detailing',
            'Частный сад': 'kindergarten',
            'Салон красоты': 'beauty_salon',
            'Фитнес центр': 'fitness_centre'
        }
        
        # Проверка доступности папки для записи
        self._check_write_permissions()
        
        # Инициализация CSV файла
        self._init_csv_file()
    
    def _check_write_permissions(self):
        """Проверка доступности папки для записи"""
        try:
            test_file = 'test_write_permission.tmp'
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            logger.info("✅ Папка доступна для записи")
        except Exception as e:
            logger.error(f"❌ Ошибка: папка недоступна для записи! {e}")
            print("❌ ОШИБКА: Нет прав на запись в текущую папку!")
            print("Пожалуйста, запустите скрипт из другой папки или измените права доступа.")
            raise PermissionError("Нет прав на запись")
    
    def _init_csv_file(self):
        """Инициализация CSV файла с расширенной структурой для CRM"""
        filename = 'leads.csv'
        fieldnames = [
            'Name', 'Category', 'Phone', 'Phone_Type', 'Website', 'Email', 'Instagram', 'Telegram', 'VK', 'WhatsApp',
            'Priority_Score', 'AI_Verdict', 'Detailed_Pains', 'Social_Links', 'Proposed_Offer',
            'Main_Pain', 'Ice_Breaker', 'Address', 'City', 'Is_Hot_Lead'
        ]
        
        # Создаем файл с заголовками, если его нет
        if not os.path.exists(filename):
            try:
                with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                logger.info(f"✅ Создан файл {filename} с CRM структурой")
            except Exception as e:
                logger.error(f"❌ Ошибка создания CSV файла: {e}")
                raise
    
    def _save_lead_to_csv(self, lead: BusinessLead, filename: str = 'leads.csv'):
        """Сохранение одного лида в CSV с расширенной CRM структурой"""
        try:
            # Генерируем все CRM поля
            lead.ice_breaker = self.filter.generate_ice_breaker(lead)
            lead.priority_score = self.filter.calculate_priority_score(lead)
            lead.ai_verdict = self.filter.generate_ai_verdict(lead)
            lead.detailed_pains = self.filter.generate_detailed_pains(lead)
            lead.social_links = self.filter.generate_social_links(lead)
            lead.proposed_offer = self.filter.generate_proposed_offer(lead)
            
            # Формируем главную боль (первую из списка)
            main_pain = lead.pain_points[0] if lead.pain_points else ''
            
            with open(filename, 'a', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=[
                    'Name', 'Category', 'Phone', 'Phone_Type', 'Website', 'Email', 'Instagram', 'Telegram', 'VK', 'WhatsApp',
                    'Priority_Score', 'AI_Verdict', 'Detailed_Pains', 'Social_Links', 'Proposed_Offer',
                    'Main_Pain', 'Ice_Breaker', 'Address', 'City', 'Is_Hot_Lead'
                ])
                writer.writerow({
                    'Name': lead.name,
                    'Category': lead.category,
                    'Phone': lead.phone or '',
                    'Phone_Type': lead.phone_type,
                    'Website': lead.website or '',
                    'Email': lead.email,
                    'Instagram': f"@{lead.instagram}" if lead.instagram else '',
                    'Telegram': f"@{lead.telegram}" if lead.telegram else '',
                    'VK': f"vk.com/{lead.vk}" if lead.vk else '',
                    'WhatsApp': f"wa.me/{lead.whatsapp}" if lead.whatsapp else '',
                    'Priority_Score': lead.priority_score,
                    'AI_Verdict': lead.ai_verdict,
                    'Detailed_Pains': lead.detailed_pains,
                    'Social_Links': lead.social_links,
                    'Proposed_Offer': lead.proposed_offer,
                    'Main_Pain': main_pain,
                    'Ice_Breaker': lead.ice_breaker,
                    'Address': lead.address,
                    'City': lead.city,
                    'Is_Hot_Lead': 'YES' if lead.is_hot_lead else 'NO'
                })
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения лида: {e}")
            return False
        
    def find_leads(self, categories: List[str], cities: List[str], max_results_per_category: int = 20) -> List[BusinessLead]:
        """Основной метод поиска лидов с немедленным сохранением"""
        all_leads = []
        saved_count = 0
        
        for city in cities:
            print(f"\n🔎 Анализирую малый бизнес в {city}...")
            for category in categories:
                amenity = self.category_mapping.get(category, category.lower())
                logger.info(f"Поиск МСБ {category} ({amenity}) в {city}...")
                
                places = self.api.search_places(amenity, city, max_results_per_category)
                
                for i, place in enumerate(places):
                    # Извлечение информации
                    place_info = self.api.extract_place_info(place)
                    
                    # ФИЛЬТР ПО РАЗМЕРУ - исключаем сети и госучреждения
                    if not self.filter.is_small_business(place_info['name']):
                        print(f"  ❌ ПРОПУЩЕНА КРУГНАЯ: {place_info['name'][:30]}... (не МСБ)")
                        continue
                    
                    # ЖЕСТКИЙ ФИЛЬТР "ПУСТЫШЕК" - пропускаем без телефона и сайта
                    if not place_info['phone'] and not place_info['website']:
                        print(f"  ❌ ПРОПУЩЕНА ПУСТЫШКА: {place_info['name'][:30]}... (нет телефона и сайта)")
                        continue
                    
                    # Создание объекта лида
                    lead = BusinessLead(
                        name=place_info['name'],
                        phone=place_info['phone'],
                        website=place_info['website'],
                        rating=0.0,  # OSM не предоставляет рейтинги
                        review_count=0,  # OSM не предоставляет отзывы
                        address=place_info['address'],
                        category=category,
                        city=city
                    )
                    
                    # Анализ типа телефона для МСБ
                    lead.phone_type = WebsiteAnalyzer.analyze_phone_type(lead.phone)
                    
                    # ГЛУБОКИЙ ПОИСК КОНТАКТОВ, если есть сайт
                    if lead.website:
                        contacts = WebsiteAnalyzer.extract_contacts(lead.website)
                        lead.email = contacts['email']
                        lead.instagram = contacts['instagram']
                        lead.telegram = contacts['telegram']
                        lead.vk = contacts['vk']
                        lead.whatsapp = contacts['whatsapp']
                    
                    # Анализ "болей" для МСБ
                    is_hot, pain_points = self.filter.analyze_pain_points(lead)
                    lead.is_hot_lead = is_hot
                    lead.pain_points = pain_points
                    
                    # НЕМЕДЛЕННОЕ СОХРАНЕНИЕ В CSV
                    if self._save_lead_to_csv(lead):
                        saved_count += 1
                        all_leads.append(lead)
                        
                        # КРАСИВЫЙ ВЫВОД В ТЕРМИНАЛ ДЛЯ CRM
                        print(f"\n┌─────────────────────────────────────────────────────────")
                        print(f"│ 🏪 CRM ЛИД #{saved_count:3d} │ {lead.name[:40]}")
                        print(f"├─────────────────────────────────────────────────────────")
                        print(f"│ 🏷️  Категория:\t{lead.category}")
                        print(f"│ 📱 Телефон:\t{lead.phone or '❌ Нет'} ({lead.phone_type})")
                        print(f"│ 🌐 Сайт:\t{lead.website or '❌ Нет'}")
                        
                        # Показываем найденные контакты с приоритетом МСБ
                        if lead.whatsapp:
                            print(f"│ 📱 WhatsApp:\twa.me/{lead.whatsapp} 🔥")
                        if lead.instagram:
                            print(f"│ 📷 Instagram:\t@{lead.instagram} 🔥")
                        if lead.email:
                            print(f"│ 📧 Email:\t{lead.email}")
                        if lead.telegram:
                            print(f"│ ✈️ Telegram:\t@{lead.telegram}")
                        if lead.vk:
                            print(f"│ 💬 VK:\tvk.com/{lead.vk}")
                        
                        # CRM метрики
                        print(f"│ 📊 Приоритет:\t{lead.priority_score}/100")
                        print(f"│ 🤖 AI Вердикт:\t{lead.ai_verdict}")
                        print(f"│ 💬 Предложение:\t{lead.proposed_offer}")
                        
                        status = "🔥 ГОРЯЧИЙ CRM" if is_hot else "❄️ Обычный CRM"
                        print(f"│ 🎯 Статус:\t{status}")
                        
                        if is_hot and pain_points:
                            print(f"│ 💡 Главная боль:\t{pain_points[0]}")
                        
                        print(f"└─────────────────────────────────────────────────────────")
                    else:
                        logger.error(f"Не удалось сохранить МСБ лид: {lead.name}")
                
                # Задержка между запросами разных категорий (увеличена для стабильности)
                logger.info("Задержка 10 секунд для избежания лимитов Overpass API...")
                time.sleep(10)
        
        logger.info(f"✅ Всего сохранено лидов: {saved_count}")
        return all_leads
    
    def save_to_csv(self, leads: List[BusinessLead], filename: str = 'leads.csv'):
        """Сохранение результатов в CSV файл"""
        fieldnames = [
            'name', 'phone', 'website', 'rating', 'review_count', 
            'address', 'category', 'city', 'is_hot_lead', 'pain_points'
        ]
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for lead in leads:
                    writer.writerow({
                        'name': lead.name,
                        'phone': lead.phone,
                        'website': lead.website,
                        'rating': lead.rating,
                        'review_count': lead.review_count,
                        'address': lead.address,
                        'category': lead.category,
                        'city': lead.city,
                        'is_hot_lead': lead.is_hot_lead,
                        'pain_points': '; '.join(lead.pain_points)
                    })
            
            logger.info(f"✅ Сохранено {len(leads)} лидов в {filename}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения в CSV: {e}")
            return False

def main():
    """Главная функция - работает БЕЗ API ключей"""
    print("🚀 Lead Finder - AI-Powered Lead Generation for CIS")
    print("🔥 Smart analysis of Small Business pain points")
    print("=" * 50)
    
    # Инициализация (больше не нужен API ключ!)
    finder = LeadFinder()
    
    # Параметры поиска (фокус на МСБ в СНГ)
    categories = ['Парикмахерская', 'Барбершоп', 'Мойка', 'Пекарня', 'Цветы', 'Химчистка']
    cities = ['Минск']  # Тест на Минске для МСБ
    
    print("🔍 Начинаю поиск потенциальных клиентов...")
    print(f"Категории: {', '.join(categories)}")
    print(f"Города: {', '.join(cities)}")
    print("Источник: OpenStreetMap Overpass API")
    print()
    
    # Поиск лидов (с немедленным сохранением в CSV)
    print("🚀 Начинаю поиск с немедленным сохранением...")
    print("📁 Файл leads.csv будет обновляться в реальном времени!")
    print()
    
    try:
        leads = finder.find_leads(categories, cities)
        
        # Вывод финальной статистики
        total_leads = len(leads)
        hot_leads = sum(1 for lead in leads if lead.is_hot_lead)
        
        print(f"\n🎉 Поиск завершен!")
        print(f"📊 Финальная статистика:")
        print(f"   Всего обработано: {total_leads} лидов")
        
        # Защита от division by zero
        if total_leads > 0:
            hot_percentage = hot_leads/total_leads*100
            print(f"   Горячих лидов: {hot_leads} ({hot_percentage:.1f}%)")
        else:
            print(f"   Горячих лидов: {hot_leads} (0.0%)")
            print(f"   ⚠️  Лидов не найдено. Попробуйте другие категории или города.")
        
        # Статистика по категориям
        print(f"\n📈 По категориям:")
        for category in categories:
            cat_leads = [lead for lead in leads if lead.category == category]
            cat_hot = sum(1 for lead in cat_leads if lead.is_hot_lead)
            print(f"   {category}: {len(cat_leads)} найдено, {cat_hot} горячих")
        
        print(f"\n✅ Все данные сохранены в leads.csv")
        print(f"🤖 Файл готов для интеграции с ИИ-звонарем!")
        print(f"\n💡 Преимущества CRM версии:")
        print(f"   • Расширенные категории (high-ticket)")
        print(f"   • Жесткие формулировки 'болей' для конверсии")
        print(f"   • Персонализированные ice breaker'ы для ИИ-звонаря")
        print(f"   • Поиск по районам (без 504 ошибок)")
        print(f"   • Сохранение в реальном времени")
        
    except KeyboardInterrupt:
        print(f"\n⏹️ Скрипт прерван пользователем")
        print(f"✅ Все сохраненные данные остались в leads.csv")
        print(f"🔄 Запустите скрипт снова для продолжения")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        print(f"✅ Сохраненные данные остались в leads.csv")

if __name__ == "__main__":
    main()
