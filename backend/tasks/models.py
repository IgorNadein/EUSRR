from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone
from employees.models import Department


class TaskPriority(models.TextChoices):
    LOW = "low", "Низкий"
    MEDIUM = "medium", "Средний"
    HIGH = "high", "Высокий"
    CRITICAL = "critical", "Критический"


class TaskBoard(models.Model):
    name = models.CharField("Название", max_length=255)
    description = models.TextField("Описание", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_task_boards",
        verbose_name="Создал",
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="task_boards",
        verbose_name="Участники",
    )
    departments = models.ManyToManyField(
        Department,
        blank=True,
        related_name="task_boards",
        verbose_name="Отделы",
    )
    is_archived = models.BooleanField("Архивная", default=False)
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Доска задач"
        verbose_name_plural = "Доски задач"
        ordering = ["name", "id"]

    def __str__(self):
        return self.name


class TaskColumn(models.Model):
    board = models.ForeignKey(
        TaskBoard,
        on_delete=models.CASCADE,
        related_name="columns",
        verbose_name="Доска",
    )
    name = models.CharField("Название", max_length=120)
    position = models.PositiveIntegerField("Позиция", default=0)
    color = models.CharField("Цвет", max_length=32, blank=True)
    is_done = models.BooleanField("Финальная колонка", default=False)
    is_archived = models.BooleanField("Архивная", default=False)
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Колонка задач"
        verbose_name_plural = "Колонки задач"
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["board", "name"],
                name="uniq_task_column_board_name",
            )
        ]

    def __str__(self):
        return f"{self.board}: {self.name}"


class TaskLabel(models.Model):
    board = models.ForeignKey(
        TaskBoard,
        on_delete=models.CASCADE,
        related_name="labels",
        verbose_name="Доска",
    )
    name = models.CharField("Название", max_length=80)
    color = models.CharField("Цвет", max_length=32, default="#38bdf8")

    class Meta:
        verbose_name = "Метка задачи"
        verbose_name_plural = "Метки задач"
        ordering = ["name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["board", "name"],
                name="uniq_task_label_board_name",
            )
        ]

    def __str__(self):
        return self.name


class Task(models.Model):
    board = models.ForeignKey(
        TaskBoard,
        on_delete=models.CASCADE,
        related_name="tasks",
        verbose_name="Доска",
    )
    column = models.ForeignKey(
        TaskColumn,
        on_delete=models.PROTECT,
        related_name="tasks",
        verbose_name="Колонка",
    )
    title = models.CharField("Название", max_length=255)
    description = models.TextField("Описание", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_tasks",
        verbose_name="Создал",
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tasks",
        verbose_name="Исполнитель",
    )
    labels = models.ManyToManyField(
        TaskLabel,
        blank=True,
        related_name="tasks",
        verbose_name="Метки",
    )
    priority = models.CharField(
        "Приоритет",
        max_length=20,
        choices=TaskPriority.choices,
        default=TaskPriority.MEDIUM,
    )
    due_date = models.DateField("Срок", null=True, blank=True)
    position = models.PositiveIntegerField("Позиция", default=0)
    completed_at = models.DateTimeField("Завершено", null=True, blank=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Задача"
        verbose_name_plural = "Задачи"
        ordering = ["position", "-created_at", "id"]
        indexes = [
            models.Index(fields=["board", "column", "position"]),
            models.Index(fields=["assignee", "due_date"]),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.column_id and self.board_id != self.column.board_id:
            self.board_id = self.column.board_id

        if self.column_id and self.column.is_done and not self.completed_at:
            self.completed_at = timezone.now()
        elif self.column_id and not self.column.is_done:
            self.completed_at = None

        super().save(*args, **kwargs)


class TaskLinkedObjectKind(models.TextChoices):
    MESSAGE = "message", "Сообщение"
    CALENDAR_EVENT = "calendar_event", "Календарное событие"
    DOCUMENT = "document", "Документ"
    REQUEST = "request", "Заявление"
    PROCUREMENT_REQUEST = "procurement_request", "Заявка на закупку"


class TaskActivityAction(models.TextChoices):
    CREATED = "created", "Создал задачу"
    UPDATED = "updated", "Обновил задачу"
    MOVED = "moved", "Переместил задачу"
    LINKED = "linked", "Связал объект"
    UNLINKED = "unlinked", "Убрал связь"


class TaskActivity(models.Model):
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="activities",
        verbose_name="Задача",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="task_activities",
        verbose_name="Исполнитель",
    )
    action = models.CharField(
        "Действие",
        max_length=32,
        choices=TaskActivityAction.choices,
    )
    object_kind = models.CharField(
        "Тип объекта",
        max_length=32,
        choices=TaskLinkedObjectKind.choices,
        blank=True,
    )
    object_id = models.PositiveBigIntegerField("ID объекта", null=True, blank=True)
    metadata = models.JSONField("Метаданные", default=dict, blank=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        verbose_name = "История задачи"
        verbose_name_plural = "История задач"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["task", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.task} - {self.action}"


class TaskLinkedObject(models.Model):
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="linked_objects",
        verbose_name="Задача",
    )
    kind = models.CharField(
        "Тип связи",
        max_length=32,
        choices=TaskLinkedObjectKind.choices,
    )
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        verbose_name="Тип объекта",
    )
    object_id = models.PositiveBigIntegerField("ID объекта")
    content_object = GenericForeignKey("content_type", "object_id")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_task_links",
        verbose_name="Связал",
    )
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    metadata = models.JSONField("Метаданные", default=dict, blank=True)

    class Meta:
        verbose_name = "Связанный объект задачи"
        verbose_name_plural = "Связанные объекты задач"
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["task", "content_type", "object_id"],
                name="uniq_task_linked_object",
            )
        ]
        indexes = [
            models.Index(fields=["task", "kind"]),
            models.Index(fields=["content_type", "object_id"]),
        ]

    def __str__(self):
        return f"{self.task} -> {self.kind}:{self.object_id}"
