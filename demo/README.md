# Запись демо

`record.mjs` ведёт интерфейс в браузере (Playwright) на живом Keitaro и после каждого шага показывает карточку с тем, что возвращает Admin API. Создаёт кампанию `test_bulygin_demo_<время>` на существующем домене и удаляет её по окончании.

```
# сервис запущен, в .env есть KEITARO_API_KEY
DEMO_URL=http://127.0.0.1:3000 node demo/record.mjs
ffmpeg -i demo/out/*.webm -c:v libx264 -crf 20 -pix_fmt yuv420p -movflags +faststart -an demo/out/demo.mp4
```

| Переменная | По умолчанию | Назначение |
|------------|--------------|------------|
| `DEMO_URL` | `http://127.0.0.1:3929` | адрес интерфейса |
| `DEMO_ENV` | `.env` | файл с `KEITARO_BASE_URL` и `KEITARO_API_KEY` |
| `DEMO_OUT` | `demo/out` | каталог записи |
| `E2E_CHROMIUM` | `/usr/bin/chromium` | браузер |

Видео в репозиторий не кладётся: готовая запись — в релизе `demo-mvp`.
