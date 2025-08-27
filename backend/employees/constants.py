# backend\employees\constants.py
GENDER_CHOICES = (
    (1, 'Мужской'),
    (2, 'Женский'),
    (0, 'Не указан'),
)


ACTION_HIRED = 'hired'
ACTION_DISMISSED = 'dismissed'
ACTION_ON_LEAVE = 'on_leave'
ACTION_RETURNED_FROM_LEAVE = 'returned_from_leave'
ACTION_ON_MATERNITY = 'on_maternity'
ACTION_RETURNED_FROM_MATERNITY = 'returned_from_maternity'
ACTION_TRANSFERRED = 'transferred'
ACTION_REHIRED = 'rehired'

ACTION_CHOICES = [
    (ACTION_HIRED, 'Принят'),
    (ACTION_DISMISSED, 'Уволен'),
    (ACTION_ON_LEAVE, 'В отпуске'),
    (ACTION_RETURNED_FROM_LEAVE, 'Вернулся из отпуска'),
    (ACTION_ON_MATERNITY, 'В декрете'),
    (ACTION_RETURNED_FROM_MATERNITY, 'Вернулся из декрета'),
    (ACTION_TRANSFERRED, 'Переведен'),
    (ACTION_REHIRED, 'Восстановлен'),
]