# 🍰 Zarządzanie Cukiernią

Aplikacja webowa do zarządzania zamówieniami produktów spożywczych w cukierni.

## Funkcjonalności

- ✅ **Zarządzanie Klientami** - dodawanie, szukanie, usuwanie klientów
- ✅ **Zarządzanie Zamówieniami** - dodawanie produktów do zamówień klientów
- ✅ **Agregacja Produktów** - widok wszystkich produktów z sumą ilości
- ✅ **Oznaczanie Dostaw** - oznaczanie zamówień jako dostarczone
- ✅ **Baza SQLite** - prosta baza danych w pliku

## Wymagania

- Python 3.7+
- Flask
- SQLite3 (wbudowany w Python)

## Instalacja

1. Zainstaluj wymagane pakiety:
```bash
pip install -r requirements.txt
```

2. Uruchom aplikację:
```bash
python app.py
```

3. Otwórz przeglądarkę na adresie:
```
http://localhost:5000
```

## Baza Danych

Aplikacja automatycznie tworzy plik `bakery.db` z tabelami:
- `customers` - dane klientów (imię, telefon)
- `products` - lista produktów
- `orders` - zamówienia (kto, co, ile, czy dostarczone)

## Jak Używać

1. **Dodaj klienta** - kliknij "Dodaj Nowego Klienta"
2. **Dodaj zamówienie** - kliknij "Szczegóły" przy kliencie i dodaj produkty
3. **Szukaj klienta** - użyj wyszukiwarki po imieniu lub numerze telefonu
4. **Oznacz dostarczone** - kliknij "Oznacz jako odebrane" - produkty będą odjęte z sumy
5. **Ogląd produktów** - strona główna pokazuje wszystkie dostępne produkty z ilościami

## Struktura Projektu

```
bakery/
├── app.py              # Backend Flask
├── requirements.txt    # Zależności
├── bakery.db          # Baza danych (tworzona automatycznie)
└── templates/
    └── index.html     # Frontend HTML/CSS/JS
```
