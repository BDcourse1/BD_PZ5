# file: calorie_finder_app.py
import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QLineEdit, QPushButton,
                             QTextEdit, QTableWidget, QTableWidgetItem,
                             QTabWidget, QHeaderView, QMessageBox, QProgressBar)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
import requests

BASE = "https://world.openfoodfacts.org"

HEADERS = {
    "User-Agent": "Darcons-Trade-CalorieFetcher/1.0 (+https://darcons-trade.example)"
}


def get_product_by_barcode(barcode: str, fields=None, lang="ru", country="ru") -> dict:
    """
    Получение конкретного продукта по штрихкоду (API v2).
    """
    if fields is None:
        fields = "code,product_name,nutriments,brands,quantity,serving_size,language,lang,lc"
    url = f"{BASE}/api/v2/product/{barcode}"
    params = {"fields": fields, "lc": lang, "cc": country}
    r = requests.get(url, headers=HEADERS, params=params, timeout=20)
    r.raise_for_status()
    return r.json()


def search_products(query: str, page_size=5, fields=None, lang="ru", country="ru") -> dict:
    """
    Поиск продуктов по тексту (Search API v2).
    Пример фильтра: можно добавлять tags и условия по нутриентам.
    """
    if fields is None:
        fields = "code,product_name,brands,nutriments,quantity,serving_size,ecoscore_grade"
    url = f"{BASE}/api/v2/search"
    params = {
        "search_terms": query,
        "fields": fields,
        "page_size": page_size,
        "lc": lang,
        "cc": country,
    }
    r = requests.get(url, headers=HEADERS, params=params, timeout=20)
    r.raise_for_status()
    return r.json()


def extract_kcal(nutriments: dict) -> dict:
    """
    Извлекает калорийность и БЖУ.
    Возвращает значения на 100 г и на порцию (если доступно).
    """
    get = nutriments.get
    data = {
        "kcal_100g": get("energy-kcal_100g") or get("energy-kcal_value"),
        "protein_100g": get("proteins_100g"),
        "fat_100g": get("fat_100g"),
        "carbs_100g": get("carbohydrates_100g"),
        "kcal_serving": get("energy-kcal_serving"),
        "protein_serving": get("proteins_serving"),
        "fat_serving": get("fat_serving"),
        "carbs_serving": get("carbohydrates_serving"),
    }
    return {k: v for k, v in data.items() if v is not None}


class SearchWorker(QThread):
    """Поток для выполнения поиска продуктов"""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, search_type, query):
        super().__init__()
        self.search_type = search_type  # 'barcode' или 'name'
        self.query = query

    def run(self):
        try:
            if self.search_type == 'barcode':
                result = get_product_by_barcode(self.query)
                # Преобразуем в формат, совместимый с таблицей
                if result.get("product"):
                    products = {"products": [result["product"]]}
                else:
                    products = {"products": []}
            else:
                products = search_products(self.query, page_size=10)

            self.finished.emit(products)
        except requests.exceptions.RequestException as e:
            self.error.emit(f"Ошибка сети: {str(e)}")
        except Exception as e:
            self.error.emit(f"Ошибка: {str(e)}")


class CalorieFinderApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Поиск калорийности продуктов - OpenFoodFacts')
        self.setGeometry(100, 100, 900, 700)

        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Основной layout
        layout = QVBoxLayout(central_widget)

        # Заголовок
        title = QLabel('Поиск калорийности продуктов')
        title.setStyleSheet('font-size: 18px; font-weight: bold; margin: 10px;')
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Создаем вкладки
        tabs = QTabWidget()
        layout.addWidget(tabs)

        # Вкладка поиска по штрихкоду
        barcode_tab = QWidget()
        barcode_layout = QVBoxLayout(barcode_tab)

        # Поле для ввода штрихкода
        barcode_input_layout = QHBoxLayout()
        barcode_input_layout.addWidget(QLabel('Штрихкод:'))
        self.barcode_input = QLineEdit()
        self.barcode_input.setPlaceholderText('Введите штрихкод продукта...')
        self.barcode_input.returnPressed.connect(self.search_by_barcode)
        barcode_input_layout.addWidget(self.barcode_input)

        self.barcode_search_btn = QPushButton('Найти')
        self.barcode_search_btn.clicked.connect(self.search_by_barcode)
        barcode_input_layout.addWidget(self.barcode_search_btn)

        barcode_layout.addLayout(barcode_input_layout)

        # Прогресс бар
        self.barcode_progress = QProgressBar()
        self.barcode_progress.setVisible(False)
        barcode_layout.addWidget(self.barcode_progress)

        # Таблица для отображения результатов
        self.barcode_table = QTableWidget()
        self.barcode_table.setColumnCount(8)
        self.barcode_table.setHorizontalHeaderLabels([
            'Штрихкод', 'Название', 'Бренд', 'Калории/100г',
            'Белки/100г', 'Жиры/100г', 'Углеводы/100г', 'Порция'
        ])
        self.barcode_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        barcode_layout.addWidget(self.barcode_table)

        # Вкладка поиска по названию
        name_tab = QWidget()
        name_layout = QVBoxLayout(name_tab)

        # Поле для ввода названия
        name_input_layout = QHBoxLayout()
        name_input_layout.addWidget(QLabel('Название:'))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText('Введите название продукта...')
        self.name_input.returnPressed.connect(self.search_by_name)
        name_input_layout.addWidget(self.name_input)

        self.name_search_btn = QPushButton('Найти')
        self.name_search_btn.clicked.connect(self.search_by_name)
        name_input_layout.addWidget(self.name_search_btn)

        name_layout.addLayout(name_input_layout)

        # Прогресс бар
        self.name_progress = QProgressBar()
        self.name_progress.setVisible(False)
        name_layout.addWidget(self.name_progress)

        # Таблица для отображения результатов
        self.name_table = QTableWidget()
        self.name_table.setColumnCount(8)
        self.name_table.setHorizontalHeaderLabels([
            'Штрихкод', 'Название', 'Бренд', 'Калории/100г',
            'Белки/100г', 'Жиры/100г', 'Углеводы/100г', 'Порция'
        ])
        self.name_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.name_table.doubleClicked.connect(self.on_product_double_click)
        name_layout.addWidget(self.name_table)

        # Добавляем вкладки
        tabs.addTab(barcode_tab, "Поиск по штрихкоду")
        tabs.addTab(name_tab, "Поиск по названию")

        # Статус бар
        self.statusBar().showMessage('Готов к поиску')

    def search_by_barcode(self):
        barcode = self.barcode_input.text().strip()
        if not barcode:
            QMessageBox.warning(self, 'Ошибка', 'Введите штрихкод')
            return

        self.barcode_search_btn.setEnabled(False)
        self.barcode_progress.setVisible(True)
        self.barcode_progress.setRange(0, 0)  # индикатор прогресса
        self.statusBar().showMessage('Поиск по штрихкоду...')

        self.search_worker = SearchWorker('barcode', barcode)
        self.search_worker.finished.connect(self.on_barcode_search_finished)
        self.search_worker.error.connect(self.on_search_error)
        self.search_worker.start()

    def search_by_name(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, 'Ошибка', 'Введите название продукта')
            return

        self.name_search_btn.setEnabled(False)
        self.name_progress.setVisible(True)
        self.name_progress.setRange(0, 0)  # индикатор прогресса
        self.statusBar().showMessage('Поиск по названию...')

        self.search_worker = SearchWorker('name', name)
        self.search_worker.finished.connect(self.on_name_search_finished)
        self.search_worker.error.connect(self.on_search_error)
        self.search_worker.start()

    def on_barcode_search_finished(self, products):
        self.barcode_search_btn.setEnabled(True)
        self.barcode_progress.setVisible(False)
        self.display_products_in_table(self.barcode_table, products)
        count = len(products.get('products', []))
        self.statusBar().showMessage(f'Найдено продуктов: {count}')

    def on_name_search_finished(self, products):
        self.name_search_btn.setEnabled(True)
        self.name_progress.setVisible(False)
        self.display_products_in_table(self.name_table, products)
        count = len(products.get('products', []))
        self.statusBar().showMessage(f'Найдено продуктов: {count}')

    def on_search_error(self, error_message):
        # Сброс состояния кнопок и прогресс-баров
        self.barcode_search_btn.setEnabled(True)
        self.name_search_btn.setEnabled(True)
        self.barcode_progress.setVisible(False)
        self.name_progress.setVisible(False)

        QMessageBox.critical(self, 'Ошибка', error_message)
        self.statusBar().showMessage('Ошибка при поиске')

    def display_products_in_table(self, table, products):
        products_list = products.get('products', [])
        table.setRowCount(len(products_list))

        for row, product in enumerate(products_list):
            # Извлекаем нутриенты
            nutriments = extract_kcal(product.get('nutriments', {}))

            # Заполняем ячейки таблицы
            table.setItem(row, 0, QTableWidgetItem(product.get('code', 'N/A')))
            table.setItem(row, 1, QTableWidgetItem(product.get('product_name', 'N/A')))
            table.setItem(row, 2, QTableWidgetItem(product.get('brands', 'N/A')))

            # Калории
            kcal = nutriments.get('kcal_100g', 'N/A')
            table.setItem(row, 3, QTableWidgetItem(str(kcal)))

            # Белки
            protein = nutriments.get('protein_100g', 'N/A')
            table.setItem(row, 4, QTableWidgetItem(str(protein)))

            # Жиры
            fat = nutriments.get('fat_100g', 'N/A')
            table.setItem(row, 5, QTableWidgetItem(str(fat)))

            # Углеводы
            carbs = nutriments.get('carbs_100g', 'N/A')
            table.setItem(row, 6, QTableWidgetItem(str(carbs)))

            # Порция
            serving = product.get('serving_size', 'N/A')
            table.setItem(row, 7, QTableWidgetItem(str(serving)))

    def on_product_double_click(self, index):
        """Показывает детальную информацию о продукте при двойном клике"""
        table = self.name_table
        row = index.row()

        product_info = {
            'Штрихкод': table.item(row, 0).text(),
            'Название': table.item(row, 1).text(),
            'Бренд': table.item(row, 2).text(),
            'Калории/100г': table.item(row, 3).text(),
            'Белки/100г': table.item(row, 4).text(),
            'Жиры/100г': table.item(row, 5).text(),
            'Углеводы/100г': table.item(row, 6).text(),
            'Порция': table.item(row, 7).text()
        }

        detail_text = "\n".join([f"{key}: {value}" for key, value in product_info.items()])
        QMessageBox.information(self, 'Детальная информация', detail_text)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = CalorieFinderApp()
    window.show()
    sys.exit(app.exec_())