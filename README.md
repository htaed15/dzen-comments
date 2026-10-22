# Комментарии — SPA (Django + Vue)

Тестовое задание dZENcode, уровень **Junior+**. Каскадные комментарии с вложениями,
CAPTCHA, предпросмотром, WebSocket-обновлениями и опциональной JWT-авторизацией.

## Возможности

- Форма: User Name (латиница/цифры), E-mail, Home page, CAPTCHA (картинка), Text.
- Разрешённые теги: `<a href title>`, `<code>`, `<i>`, `<strong>`; проверка закрытия и вложенности
  (клиент + сервер), остальной HTML вырезается (`nh3`, белый список).
- Каскадные ответы любой глубины; в таблице только заглавные комментарии.
- Сортировка по User Name, E-mail, дате (↑/↓), по умолчанию LIFO; пагинация по 25.
- Вложения: JPG/GIF/PNG (пропорциональное уменьшение до 320×240) и TXT до 100 КБ; просмотр в lightbox.
- Предпросмотр без перезагрузки, панель тегов `[i] [strong] [code] [a]`.
- Защита: XSS (санитизация на входе + экранирование), SQL-инъекции (только ORM, белый список полей сортировки).

### Junior+

| Инструмент | Где используется |
|---|---|
| Queue (Celery + Redis) | обработка вложений, e-mail автору комментария при ответе |
| Cache (Redis) | кеш списков (версионный ключ), хранение CAPTCHA с TTL |
| Events (Django signals) | `post_save` → сброс кеша, задачи Celery, событие WebSocket |
| JWT (simplejwt) | регистрация/вход; авторизованный пользователь пишет без CAPTCHA |
| WebSocket (Channels) | новые комментарии у всех клиентов без перезагрузки |

## Запуск (Docker)

```bash
cp .env.example .env
docker compose up --build
```

Приложение: http://localhost:8080

## Локальная разработка без Docker

Без `REDIS_URL` и `POSTGRES_HOST` проект работает на SQLite, кеше в памяти, а Celery выполняет
задачи синхронно.

```bash
cd backend
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver        # http://localhost:8000
python manage.py test comments    # тесты

cd ../frontend
npm install
npm run dev                       # http://localhost:5173 (прокси на :8000)
```

## API

| Метод | URL | Назначение |
|---|---|---|
| GET | `/api/comments/?ordering=-created_at&page=1` | заглавные комментарии с деревом ответов |
| POST | `/api/comments/` | создать (multipart: user_name, email, home_page, text, parent, captcha_key, captcha_answer, file) |
| POST | `/api/comments/preview/` | предпросмотр (тот же санитайзер) |
| GET | `/api/captcha/` | `{key, image}` |
| POST | `/api/auth/register/`, `/api/auth/token/`, `/api/auth/token/refresh/` | JWT |
| WS | `/ws/comments/` | события `comment.created`, `comment.updated` |

`ordering`: `user_name`, `email`, `created_at` (с `-` для убывания).

## Структура

```
backend/comments/
  models.py       Author, Comment, Attachment
  services/       HtmlSanitizer, CaptchaService, AttachmentValidator/Processor
  signals.py      события -> кеш, Celery, WebSocket
  tasks.py        Celery-задачи
  consumers.py    WebSocket
frontend/src/     Vue 3: App, CommentForm, CommentNode, Lightbox, AuthPanel
docs/schema.sql   схема для MySQL Workbench
```

## Схема БД

`docs/schema.sql` импортируется в MySQL Workbench: *File → Import → Reverse Engineer MySQL Create Script*.
