from django.core.management.base import BaseCommand

from comments.models import Comment, Profile

NAMES = ["alice", "bob", "carol", "dave", "eve"]
TEXTS = [
    "Привет всем! Это <strong>первый</strong> комментарий.",
    "Кто-нибудь пробовал <code>docker compose up</code>? У меня всё поднялось с первого раза.",
    "Интересное решение, особенно <i>кеш списка</i> на Redis.",
    "Таблица с сортировкой удобная, проверил по имени и по дате.",
    "Отличный проект, подробности на <a href=\"https://github.com/htaed15/dzen-comments\">GitHub</a>.",
    "Тестовый комментарий для проверки пагинации.",
]


class Command(BaseCommand):
    help = "Создаёт демо-комментарии (30 заглавных и несколько ответов) для показа приложения."

    def handle(self, *args, **options):
        if Profile.objects.filter(username__in=NAMES).exists():
            self.stdout.write("Демо-данные уже есть, ничего не делаю.")
            return
        profiles = [
            Profile.objects.create(username=n, email=f"{n}@example.com") for n in NAMES
        ]
        roots = []
        for i in range(30):
            text = f"{TEXTS[i % len(TEXTS)]} (№{i + 1})"
            roots.append(
                Comment.objects.create(
                    profile=profiles[i % len(profiles)], text=text, ip_address="127.0.0.1"
                )
            )
        # несколько ответов, чтобы был виден каскад
        for k, root in enumerate(roots[-3:]):
            reply = Comment.objects.create(
                profile=profiles[(k + 1) % len(profiles)],
                parent=root,
                root=root,
                text="Согласен, ответ на комментарий.",
                ip_address="127.0.0.1",
            )
            Comment.objects.create(
                profile=profiles[(k + 2) % len(profiles)],
                parent=reply,
                root=root,
                text="А вот <i>ответ на ответ</i>, каскад работает.",
                ip_address="127.0.0.1",
            )
        self.stdout.write(self.style.SUCCESS("Создано 30 комментариев и 6 ответов."))
