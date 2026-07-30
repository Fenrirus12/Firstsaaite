# Help-student

Похожий на `proseprincess.ru` лендинг для услуг по подготовке учебных работ.

## Запуск

На Windows можно запустить сайт двойным кликом по файлу:

```bat
start_site.bat
```

Он откроет сайт в браузере по адресу `http://127.0.0.1:8000`.

Также можно запустить вручную:

```bash
python server.py
```

После запуска сайт будет доступен по адресу `http://127.0.0.1:8000`.

Админ-панель: `http://127.0.0.1:8000/admin`

По умолчанию:

- логин: `admin`
- пароль: `change-me-please`

Лучше сразу переопределить через переменные окружения:

```bash
$env:ADMIN_USERNAME="your-login"
$env:ADMIN_PASSWORD="strong-password"
python server.py
```

## Деплой

Проект готов к деплою на платформах, которые запускают Python-приложения через `Procfile`.

1. Загрузите папку проекта в GitHub-репозиторий.
2. На хостинге создайте новый проект из этого репозитория.
3. Укажите переменные окружения:

```bash
ADMIN_USERNAME=your-login
ADMIN_PASSWORD=strong-password
```

4. Команда запуска уже описана в `Procfile`:

```bash
web: python server.py
```

Сервер автоматически слушает порт из переменной `PORT`, которую обычно выдаёт хостинг.

## Что внутри

- `static/index.html` — разметка лендинга
- `static/styles.css` — стили
- `static/app.js` — интерактив, отправка заявки и отзывов
- `static/admin.html` — интерфейс админ-панели
- `static/admin.js` — загрузка заявок, фильтры и модерация отзывов
- `static/admin-chats.html` — отдельная страница админских чатов
- `static/admin-chats.js` — логика списка пользователей и переписки
- `server.py` — backend на стандартной библиотеке Python
- `data/requests.json` — заявки, созданные через форму
- `data/reviews.json` — отзывы со статусами `pending/approved/rejected`
- `data/users.json` — зарегистрированные пользователи
- `data/sessions.json` — пользовательские сессии
- `data/messages.json` — сообщения в чатах пользователь-админ
