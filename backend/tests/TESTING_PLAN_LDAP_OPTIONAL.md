# План тестирования: Опциональная интеграция с LDAP

## Цель тестирования
Проверить корректность работы системы в двух режимах:
1. **LDAP_ENABLED=True** - полная интеграция с LDAP (существующая функциональность)
2. **LDAP_ENABLED=False** - автономная работа без LDAP (новая функциональность)

## Конфигурация окружения

### Режим 1: С LDAP (LDAP_ENABLED=True)
```bash
export LDAP_ENABLED=true
export LDAP_SERVER_URI=ldap://your-ldap-server:389
export LDAP_BIND_DN=CN=admin,DC=example,DC=com
export LDAP_BIND_PASSWORD=your-password
export LDAP_BASE_DN=DC=example,DC=com
export LDAP_USERS_BASE=OU=Users,DC=example,DC=com
export LDAP_GROUPS_BASE=OU=Groups,DC=example,DC=com
export LDAP_UPN_SUFFIX=@example.com
```

### Режим 2: Без LDAP (LDAP_ENABLED=False)
```bash
export LDAP_ENABLED=false
# Все остальные LDAP настройки можно не задавать
```

---

## 1. Тестирование вспомогательных функций

### 1.1 Функция `_is_ldap_enabled()`
| ID | Сценарий | LDAP_ENABLED | Ожидаемый результат |
|----|----------|--------------|---------------------|
| H1 | Проверка с LDAP | True | Возвращает True |
| H2 | Проверка без LDAP | False | Возвращает False |
| H3 | LDAP_ENABLED не задан | (не установлен) | Возвращает False (по умолчанию) |

### 1.2 Функция `_ldap_try(fn)`
| ID | Сценарий | LDAP_ENABLED | Действие | Ожидаемый результат |
|----|----------|--------------|----------|---------------------|
| H4 | Успешное выполнение | True | fn() успешна | Возвращает None |
| H5 | Ошибка LDAP | True | fn() бросает DirectoryLdapError | Возвращает Response(502) |
| H6 | LDAP отключен | False | fn() не вызывается | Возвращает None |
| H7 | Ошибка DirectoryServiceError | True | fn() бросает DirectoryServiceError | Возвращает Response(502) |

---

## 2. Тестирование RegisterAPIView

### 2.1 Регистрация пользователя (POST /api/v1/register/)

#### С LDAP (LDAP_ENABLED=True)
| ID | Сценарий | Тест-данные | Ожидаемый результат |
|----|----------|-------------|---------------------|
| R1 | Успешная регистрация | Валидные данные (email, пароль, имя, телефон) | • Создан пользователь в LDAP (disabled)<br>• Пароль установлен в LDAP<br>• Создана запись в БД (unusable_password)<br>• is_active=False<br>• Отправлено письмо верификации<br>• HTTP 201 |
| R2 | Регистрация с аватаром | + файл avatar | • Аватар загружен в LDAP<br>• Сохранён в БД<br>• HTTP 201 |
| R3 | Дублирование email | Email уже существует | HTTP 400 "email_exists" |
| R4 | Дублирование телефона | Телефон уже существует | HTTP 400 "phone_exists" |
| R5 | LDAP недоступен | LDAP сервер не отвечает | HTTP 502 "ldap_error" |
| R6 | Ошибка создания в БД | БД недоступна после LDAP | • LDAP пользователь удалён (rollback)<br>• HTTP 500 |

#### Без LDAP (LDAP_ENABLED=False)
| ID | Сценарий | Тест-данные | Ожидаемый результат |
|----|----------|-------------|---------------------|
| R7 | Успешная регистрация | Валидные данные | • Создан пользователь только в БД<br>• Пароль установлен в БД (set_password)<br>• is_active=False<br>• Письмо верификации отправлено<br>• HTTP 201 |
| R8 | Регистрация с аватаром | + файл avatar | • Аватар сохранён в media/<br>• HTTP 201 |
| R9 | Дублирование данных | Email/телефон существует | HTTP 400 |

**Проверки после регистрации:**
```python
# С LDAP
assert Employee.objects.filter(email=test_email).exists()
assert not user.has_usable_password()  # Пароль в LDAP
assert LdapSyncState.objects.filter(model='employee', object_pk=user.id).exists()

# Без LDAP
assert Employee.objects.filter(email=test_email).exists()
assert user.has_usable_password()  # Пароль в БД
assert user.check_password(test_password)
```

---

## 3. Тестирование VerifyEmailAPIView

### 3.1 Верификация email (POST /api/v1/verify-email/)

#### С LDAP (LDAP_ENABLED=True)
| ID | Сценарий | Предусловия | Ожидаемый результат |
|----|----------|-------------|---------------------|
| V1 | Успешная верификация | Пользователь существует, не верифицирован | • is_active=True в БД<br>• Активирован в LDAP (enabled)<br>• HTTP 200 |
| V2 | Повторная верификация | Уже верифицирован | HTTP 400 "already_verified" |
| V3 | Неверный токен | Токен не существует/истёк | HTTP 404 "user_not_found" |
| V4 | LDAP ошибка активации | LDAP недоступен | HTTP 502 с деталями ошибки |

#### Без LDAP (LDAP_ENABLED=False)
| ID | Сценарий | Предусловия | Ожидаемый результат |
|----|----------|-------------|---------------------|
| V5 | Успешная верификация | Пользователь не верифицирован | • is_active=True в БД<br>• HTTP 200 |
| V6 | Повторная верификация | Уже верифицирован | HTTP 400 |

**Проверки после верификации:**
```python
# С LDAP
assert user.is_active
assert ldap_user_is_enabled(user.ldap_dn)

# Без LDAP
assert user.is_active
assert user.check_password(original_password)  # Пароль сохранён
```

---

## 4. Тестирование DepartmentViewSet

### 4.1 Создание отдела (POST /api/v1/departments/)

#### С LDAP (LDAP_ENABLED=True)
| ID | Сценарий | Тест-данные | Ожидаемый результат |
|----|----------|-------------|---------------------|
| D1 | Создание отдела | name, description | • OU создан в LDAP<br>• Запись в БД<br>• HTTP 201 |
| D2 | Создание с главой | + head_id | • OU создан<br>• head установлен через DirectoryService<br>• HTTP 201 |
| D3 | LDAP ошибка | LDAP недоступен | HTTP 502 |
| D4 | Ошибка БД после LDAP | БД недоступна | • OU удалён (rollback)<br>• HTTP 500 |

#### Без LDAP (LDAP_ENABLED=False)
| ID | Сценарий | Тест-данные | Ожидаемый результат |
|----|----------|-------------|---------------------|
| D5 | Создание отдела | name, description | • Только запись в БД<br>• HTTP 201 |
| D6 | Создание с главой | + head_id | • Запись в БД с head<br>• HTTP 201 |

### 4.2 Обновление отдела (PATCH /api/v1/departments/{id}/)

#### С LDAP (LDAP_ENABLED=True)
| ID | Сценарий | Изменения | Ожидаемый результат |
|----|----------|-----------|---------------------|
| D7 | Изменение имени | name="New Name" | • OU переименован в LDAP<br>• Обновлено в БД<br>• HTTP 200 |
| D8 | Смена главы | head_id=new_head | • set_head() в LDAP<br>• head_appointed_at установлен<br>• HTTP 200 |
| D9 | Удаление главы | head_id=null | • set_head(None) в LDAP<br>• head=null в БД<br>• HTTP 200 |

#### Без LDAP (LDAP_ENABLED=False)
| ID | Сценарий | Изменения | Ожидаемый результат |
|----|----------|-----------|---------------------|
| D10 | Изменение имени | name="New Name" | • Обновлено только в БД<br>• HTTP 200 |
| D11 | Смена главы | head_id=new_head | • head обновлён в БД<br>• head_appointed_at установлен<br>• HTTP 200 |

### 4.3 Управление участниками отдела

#### add_member (POST /api/v1/departments/{id}/add-member/)

##### С LDAP (LDAP_ENABLED=True)
| ID | Сценарий | Данные | Ожидаемый результат |
|----|----------|--------|---------------------|
| D12 | Добавление участника | employee_id | • Пользователь MOVE в OU отдела в LDAP<br>• DepartmentMember создан/активирован<br>• HTTP 200 |
| D13 | Повторное добавление | Уже участник | • Активация существующей связи<br>• HTTP 200 |
| D14 | LDAP ошибка | LDAP недоступен | HTTP 502 |

##### Без LDAP (LDAP_ENABLED=False)
| ID | Сценарий | Данные | Ожидаемый результат |
|----|----------|--------|---------------------|
| D15 | Добавление участника | employee_id | • DepartmentMember создан/активирован в БД<br>• HTTP 200 |

#### remove_member (POST /api/v1/departments/{id}/remove-member/)

##### С LDAP (LDAP_ENABLED=True)
| ID | Сценарий | Данные | Ожидаемый результат |
|----|----------|--------|---------------------|
| D16 | Удаление участника | employee_id | • Пользователь MOVE обратно в Users OU<br>• is_active=False в DepartmentMember<br>• HTTP 200 |
| D17 | Удаление несуществующего | Нет такого участника | HTTP 404 |

##### Без LDAP (LDAP_ENABLED=False)
| ID | Сценарий | Данные | Ожидаемый результат |
|----|----------|--------|---------------------|
| D18 | Удаление участника | employee_id | • is_active=False в БД<br>• HTTP 200 |

### 4.4 set_member_role (POST /api/v1/departments/{id}/set-member-role/)

#### С LDAP (LDAP_ENABLED=True)
| ID | Сценарий | Данные | Ожидаемый результат |
|----|----------|--------|---------------------|
| D19 | Назначение роли | employee_id, role_id | • Роль назначена в LDAP (группы)<br>• role обновлена в БД<br>• HTTP 200 |
| D20 | Снятие роли | employee_id, role_id=null | • Роли удалены в LDAP<br>• role=null в БД<br>• HTTP 200 |

#### Без LDAP (LDAP_ENABLED=False)
| ID | Сценарий | Данные | Ожидаемый результат |
|----|----------|--------|---------------------|
| D21 | Назначение роли | employee_id, role_id | • role обновлена только в БД<br>• HTTP 200 |

### 4.5 Удаление отдела (DELETE /api/v1/departments/{id}/)

#### С LDAP (LDAP_ENABLED=True)
| ID | Сценарий | Условия | Ожидаемый результат |
|----|----------|---------|---------------------|
| D22 | Удаление пустого отдела | Нет участников | • OU удалён в LDAP<br>• Удалено из БД<br>• HTTP 204 |
| D23 | Удаление с участниками | Есть активные участники | • OU удалён<br>• Участники перемещены в Users OU<br>• HTTP 204 |
| D24 | LDAP ошибка без force_db | LDAP недоступен, force_db=false | HTTP 502 |
| D25 | LDAP ошибка с force_db | LDAP недоступен, force_db=true | • БД удалена несмотря на LDAP<br>• HTTP 204 |

#### Без LDAP (LDAP_ENABLED=False)
| ID | Сценарий | Условия | Ожидаемый результат |
|----|----------|---------|---------------------|
| D26 | Удаление отдела | Любые условия | • Удалено из БД<br>• HTTP 204 |

---

## 5. Тестирование EmployeeViewSet

### 5.1 Создание сотрудника (POST /api/v1/employees/)

#### С LDAP (LDAP_ENABLED=True)
| ID | Сценарий | Данные | Ожидаемый результат |
|----|----------|--------|---------------------|
| E1 | Создание базовое | email, имя, пароль | • Пользователь в LDAP<br>• Запись в БД<br>• HTTP 201 |
| E2 | Создание с позицией | + position_id | • Создан в LDAP<br>• assign_position() вызван<br>• Группы позиции назначены<br>• HTTP 201 |
| E3 | Создание с аватаром | + avatar file | • Аватар в LDAP<br>• HTTP 201 |
| E4 | LDAP ошибка | LDAP недоступен | HTTP 502 |

#### Без LDAP (LDAP_ENABLED=False)
| ID | Сценарий | Данные | Ожидаемый результат |
|----|----------|--------|---------------------|
| E5 | Создание базовое | email, имя, пароль | • Только в БД<br>• Пароль через set_password()<br>• HTTP 201 |
| E6 | Создание с позицией | + position_id | • Создан в БД<br>• position установлена<br>• Группы через M2M<br>• HTTP 201 |

### 5.2 Обновление сотрудника (PATCH /api/v1/employees/{id}/)

#### С LDAP (LDAP_ENABLED=True)
| ID | Сценарий | Изменения | Ожидаемый результат |
|----|----------|-----------|---------------------|
| E7 | Обновление имени | first_name, last_name | • update_user() в LDAP<br>• Обновлено в БД<br>• HTTP 200 |
| E8 | Смена email | email="new@mail.com" | • Email обновлён в LDAP<br>• Обновлён в БД<br>• HTTP 200 |
| E9 | Смена позиции | position_id=new_position | • Позиция обновлена в LDAP<br>• Группы пересчитаны<br>• HTTP 200 |
| E10 | Удаление позиции | position=null | • Позиция удалена в LDAP<br>• position=null в БД<br>• HTTP 200 |
| E11 | Обновление аватара | + новый avatar | • Аватар обновлён в LDAP<br>• Сохранён в БД<br>• HTTP 200 |
| E12 | Перемещение в отдел | department_dn=dept_dn | • MOVE в LDAP<br>• HTTP 200 |
| E13 | Назначение групп | group_cns=['CN=Group1',...] | • Группы назначены в LDAP<br>• HTTP 200 |

#### Без LDAP (LDAP_ENABLED=False)
| ID | Сценарий | Изменения | Ожидаемый результат |
|----|----------|-----------|---------------------|
| E14 | Обновление всех полей | first_name, last_name, email, phone, position, avatar | • Все обновлено в БД<br>• Аватар сохранён в media/<br>• HTTP 200 |
| E15 | Смена позиции | position_id=new_position | • Позиция обновлена в БД<br>• Группы через M2M<br>• HTTP 200 |

**Проверки:**
```python
# С LDAP
user = Employee.objects.get(id=test_id)
ldap_user = DirectoryService().get_user_by_dn(user.ldap_dn)
assert ldap_user['givenName'] == user.first_name
assert ldap_user['sn'] == user.last_name

# Без LDAP
user = Employee.objects.get(id=test_id)
assert user.first_name == expected_first_name
assert user.position_id == expected_position_id
```

---

## 6. Тестирование PositionViewSet

### 6.1 CRUD позиций

#### С LDAP (LDAP_ENABLED=True)
| ID | Сценарий | Действие | Ожидаемый результат |
|----|----------|----------|---------------------|
| P1 | Создание позиции | POST /api/v1/positions/ | • Позиция в БД<br>• reconcile_position() вызван<br>• Группа создана в LDAP<br>• HTTP 201 |
| P2 | Обновление позиции | PATCH /api/v1/positions/{id}/ | • Обновлено в БД<br>• reconcile_position() вызван<br>• HTTP 200 |
| P3 | Удаление позиции | DELETE /api/v1/positions/{id}/ | • delete_position_group() вызван<br>• Удалено из БД<br>• HTTP 204 |
| P4 | Назначение групп | POST /positions/{id}/set-groups | • groups.set() в БД<br>• reconcile_position() синхронизирует LDAP<br>• HTTP 200 |
| P5 | Добавление групп | POST /positions/{id}/add-groups | • groups.add() в БД<br>• reconcile_position()<br>• HTTP 200 |
| P6 | Удаление групп | POST /positions/{id}/remove-groups | • groups.remove() в БД<br>• reconcile_position()<br>• HTTP 200 |

#### Без LDAP (LDAP_ENABLED=False)
| ID | Сценарий | Действие | Ожидаемый результат |
|----|----------|----------|---------------------|
| P7 | Создание позиции | POST /api/v1/positions/ | • Только в БД<br>• LDAP не вызывается<br>• HTTP 201 |
| P8 | Обновление позиции | PATCH /api/v1/positions/{id}/ | • Обновлено в БД<br>• HTTP 200 |
| P9 | Удаление позиции | DELETE /api/v1/positions/{id}/ | • Удалено из БД<br>• HTTP 204 |
| P10 | Управление группами | set/add/remove-groups | • Только M2M в БД<br>• HTTP 200 |

**Проверки _ldap_try():**
```python
# _ldap_try() должен возвращать None в обоих случаях:
# - LDAP_ENABLED=True и операция успешна → None
# - LDAP_ENABLED=False → None (операция пропущена)

# Это не должно блокировать дальнейшее выполнение
```

---

## 7. Тестирование GroupViewSet

### 7.1 Создание группы (POST /api/v1/groups/)

#### С LDAP (LDAP_ENABLED=True)
| ID | Сценарий | Данные | Ожидаемый результат |
|----|----------|--------|---------------------|
| G1 | Создание группы | name, description | • Группа создана в LDAP<br>• Запись в БД<br>• HTTP 201 |
| G2 | С permissions | + permissions=[1,2,3] | • Группа в LDAP<br>• Permissions в БД<br>• HTTP 201 |
| G3 | LDAP ошибка | LDAP недоступен | HTTP 502 |
| G4 | Ошибка БД | БД сбой после LDAP | • Группа удалена из LDAP (rollback)<br>• HTTP 500 |

#### Без LDAP (LDAP_ENABLED=False)
| ID | Сценарий | Данные | Ожидаемый результат |
|----|----------|--------|---------------------|
| G5 | Создание группы | name, description, permissions | • Только в БД<br>• Permissions через M2M<br>• HTTP 201 |

### 7.2 Обновление группы (PATCH /api/v1/groups/{id}/)

#### С LDAP (LDAP_ENABLED=True)
| ID | Сценарий | Изменения | Ожидаемый результат |
|----|----------|-----------|---------------------|
| G6 | Переименование | name="New Name" | • group_rename() в LDAP<br>• Обновлено в БД<br>• HTTP 200 |
| G7 | Изменение описания | ldap_description="..." | • group_set_description() в LDAP<br>• HTTP 200 |
| G8 | Группа не найдена в LDAP | _resolve_group_dn() → None | HTTP 404 |

#### Без LDAP (LDAP_ENABLED=False)
| ID | Сценарий | Изменения | Ожидаемый результат |
|----|----------|-----------|---------------------|
| G9 | Переименование | name="New Name" | • Обновлено в БД<br>• HTTP 200 |

### 7.3 Action методы группы

#### rename (POST /api/v1/groups/{id}/rename/)

##### С LDAP (LDAP_ENABLED=True)
| ID | Сценарий | Данные | Ожидаемый результат |
|----|----------|--------|---------------------|
| G10 | Переименование | new_name="NewName" | • group_rename() в LDAP<br>• name обновлён в БД<br>• HTTP 200 |
| G11 | LDAP ошибка | LDAP недоступен | HTTP 502 |

##### Без LDAP (LDAP_ENABLED=False)
| ID | Сценарий | Данные | Ожидаемый результат |
|----|----------|--------|---------------------|
| G12 | Переименование | new_name="NewName" | • Обновлено в БД<br>• HTTP 200 |

#### set_description (POST /api/v1/groups/{id}/set-description/)

##### С LDAP (LDAP_ENABLED=True)
| ID | Сценарий | Данные | Ожидаемый результат |
|----|----------|--------|---------------------|
| G13 | Установка описания | description="..." | • group_set_description() в LDAP<br>• HTTP 200 |

##### Без LDAP (LDAP_ENABLED=False)
| ID | Сценарий | Данные | Ожидаемый результат |
|----|----------|--------|---------------------|
| G14 | Установка описания | description="..." | • Ничего не происходит (нет поля в БД)<br>• HTTP 200 |

#### members (GET /api/v1/groups/{id}/members/)

##### С LDAP (LDAP_ENABLED=True)
| ID | Сценарий | Условия | Ожидаемый результат |
|----|----------|---------|---------------------|
| G15 | Получение участников | Группа существует | • group_list_members() из LDAP<br>• Сопоставление с БД через LdapSyncState<br>• HTTP 200 {"dns": [...], "employees": [...]} |

##### Без LDAP (LDAP_ENABLED=False)
| ID | Сценарий | Условия | Ожидаемый результат |
|----|----------|---------|---------------------|
| G16 | Получение участников | Группа существует | • Участники из БД (grp.user_set.all())<br>• HTTP 200 {"dns": [], "employees": [...]} |

#### add_members (POST /api/v1/groups/{id}/add-members/)

##### С LDAP (LDAP_ENABLED=True)
| ID | Сценарий | Данные | Ожидаемый результат |
|----|----------|--------|---------------------|
| G17 | Добавление через DN | member_dns=['CN=User1,...'] | • group_add_members() в LDAP<br>• user_set.add() в БД<br>• HTTP 200 |
| G18 | Добавление через ID | member_ids=[1,2,3] | • ID→DN преобразование<br>• Добавлены в LDAP и БД<br>• HTTP 200 |
| G19 | Ошибка БД | БД сбой после LDAP | • group_remove_members() (rollback)<br>• HTTP 500 |

##### Без LDAP (LDAP_ENABLED=False)
| ID | Сценарий | Данные | Ожидаемый результат |
|----|----------|--------|---------------------|
| G20 | Добавление участников | member_ids=[1,2,3] | • user_set.add() в БД<br>• HTTP 200 |

#### remove_members (POST /api/v1/groups/{id}/remove-members/)

##### С LDAP (LDAP_ENABLED=True)
| ID | Сценарий | Данные | Ожидаемый результат |
|----|----------|--------|---------------------|
| G21 | Удаление участников | member_dns/member_ids | • group_remove_members() в LDAP<br>• user_set.remove() в БД<br>• HTTP 200 |
| G22 | Ошибка БД | БД сбой после LDAP | • group_add_members() (rollback)<br>• HTTP 500 |

##### Без LDAP (LDAP_ENABLED=False)
| ID | Сценарий | Данные | Ожидаемый результат |
|----|----------|--------|---------------------|
| G23 | Удаление участников | member_ids=[1,2,3] | • user_set.remove() в БД<br>• HTTP 200 |

#### replace_members (POST /api/v1/groups/{id}/replace-members/)

##### С LDAP (LDAP_ENABLED=True)
| ID | Сценарий | Данные | Ожидаемый результат |
|----|----------|--------|---------------------|
| G24 | Замена состава | member_dns/member_ids | • Сохранён старый состав<br>• group_replace_members() в LDAP<br>• user_set.set() в БД<br>• HTTP 200 |
| G25 | Ошибка БД | БД сбой после LDAP | • group_replace_members(prev_dns) (rollback)<br>• HTTP 500 |

##### Без LDAP (LDAP_ENABLED=False)
| ID | Сценарий | Данные | Ожидаемый результат |
|----|----------|--------|---------------------|
| G26 | Замена состава | member_ids=[...] | • user_set.set() в БД<br>• HTTP 200 |

### 7.4 Удаление группы (DELETE /api/v1/groups/{id}/)

#### С LDAP (LDAP_ENABLED=True)
| ID | Сценарий | Параметры | Ожидаемый результат |
|----|----------|-----------|---------------------|
| G27 | Удаление группы | force_db=false | • group_delete() в LDAP<br>• Удалено из БД<br>• HTTP 204 |
| G28 | LDAP ошибка без force | force_db=false, LDAP недоступен | HTTP 502 |
| G29 | LDAP ошибка с force | force_db=true, LDAP недоступен | • Игнорируем LDAP<br>• Удалено из БД<br>• HTTP 204 |

#### Без LDAP (LDAP_ENABLED=False)
| ID | Сценарий | Параметры | Ожидаемый результат |
|----|----------|-----------|---------------------|
| G30 | Удаление группы | Любые | • Удалено из БД<br>• HTTP 204 |

### 7.5 Список групп (GET /api/v1/groups/)

#### С LDAP (LDAP_ENABLED=True)
| ID | Сценарий | Условия | Ожидаемый результат |
|----|----------|---------|---------------------|
| G31 | Получение списка | Любые | • sync_groups_catalog() вызван (throttled)<br>• Список из БД<br>• HTTP 200 |

#### Без LDAP (LDAP_ENABLED=False)
| ID | Сценарий | Условия | Ожидаемый результат |
|----|----------|---------|---------------------|
| G32 | Получение списка | Любые | • Список из БД<br>• HTTP 200 |

---

## 8. Интеграционные тесты

### 8.1 Сквозной сценарий: Регистрация → Верификация → Назначение позиции

#### С LDAP
| Шаг | Действие | Проверка |
|-----|----------|----------|
| 1 | POST /api/v1/register/ | Пользователь в LDAP (disabled) и БД (inactive) |
| 2 | POST /api/v1/verify-email/ | Активирован в LDAP и БД |
| 3 | PATCH /api/v1/employees/{id}/ (position_id) | Группы позиции назначены в LDAP |
| 4 | GET /api/v1/employees/{id}/ | position корректна, is_active=true |

#### Без LDAP
| Шаг | Действие | Проверка |
|-----|----------|----------|
| 1 | POST /api/v1/register/ | Пользователь только в БД, пароль установлен |
| 2 | POST /api/v1/verify-email/ | is_active=true в БД |
| 3 | PATCH /api/v1/employees/{id}/ (position_id) | Позиция обновлена, группы через M2M |
| 4 | Аутентификация | EmailOrPhoneBackend работает, пароль проверяется из БД |

### 8.2 Сквозной сценарий: Создание отдела → Добавление участника → Назначение роли

#### С LDAP
| Шаг | Действие | Проверка |
|-----|----------|----------|
| 1 | POST /api/v1/departments/ | OU создан в LDAP |
| 2 | POST /departments/{id}/add-member/ | Пользователь перемещён в OU |
| 3 | POST /departments/{id}/set-member-role/ | Роли назначены через LDAP группы |

#### Без LDAP
| Шаг | Действие | Проверка |
|-----|----------|----------|
| 1 | POST /api/v1/departments/ | Запись в БД |
| 2 | POST /departments/{id}/add-member/ | DepartmentMember создан в БД |
| 3 | POST /departments/{id}/set-member-role/ | role обновлена в БД |

### 8.3 Сценарий: Создание группы → Добавление участников → Проверка permissions

#### С LDAP
| Шаг | Действие | Проверка |
|-----|----------|----------|
| 1 | POST /api/v1/groups/ (+ permissions) | Группа в LDAP, permissions в БД |
| 2 | POST /groups/{id}/add-members/ | Участники добавлены в LDAP группу и БД |
| 3 | Проверка прав пользователя | user.has_perm() работает корректно |

#### Без LDAP
| Шаг | Действие | Проверка |
|-----|----------|----------|
| 1 | POST /api/v1/groups/ (+ permissions) | Группа и permissions в БД |
| 2 | POST /groups/{id}/add-members/ | user_set.add() в БД |
| 3 | Проверка прав | user.has_perm() работает через Django permissions |

---

## 9. Тесты граничных условий и ошибок

### 9.1 Переключение режима во время работы

| ID | Сценарий | Действия | Ожидаемый результат |
|----|----------|----------|---------------------|
| B1 | LDAP→No LDAP | 1. Создать пользователя с LDAP<br>2. Отключить LDAP<br>3. Обновить пользователя | • Обновление работает только с БД<br>• Данные не теряются |
| B2 | No LDAP→LDAP | 1. Создать пользователя без LDAP<br>2. Включить LDAP<br>3. Обновить пользователя | • Обновление пытается синхронизировать с LDAP<br>• Может вернуть 502 если пользователя нет в LDAP |

### 9.2 Частичные сбои LDAP

| ID | Сценарий | Условия | Ожидаемый результат |
|----|----------|---------|---------------------|
| B3 | LDAP timeout | LDAP_ENABLED=True, LDAP не отвечает | HTTP 502 с деталями ошибки |
| B4 | LDAP частичный сбой | Создание в LDAP OK, обновление FAIL | Зависит от операции - либо rollback, либо 502 |
| B5 | БД сбой после LDAP | LDAP OK, БД FAIL | Rollback LDAP операции, HTTP 500 |

### 9.3 Некорректные данные

| ID | Сценарий | Данные | Ожидаемый результат |
|----|----------|--------|---------------------|
| B6 | LDAP_ENABLED не boolean | "yes"/"no"/"1"/"0" | Корректно обрабатывается через .lower() == "true" |
| B7 | Отсутствующие LDAP настройки | LDAP_ENABLED=True, но нет SERVER_URI | Ошибка при инициализации DirectoryService |
| B8 | Некорректный DN | Попытка работы с несуществующим DN | HTTP 404 или 502 в зависимости от метода |

---

## 10. Тесты производительности

### 10.1 Массовые операции

| ID | Сценарий | Параметры | Проверка |
|----|----------|-----------|----------|
| P1 | Массовая регистрация | 100 пользователей | • С LDAP: время создания < 30s<br>• Без LDAP: время < 10s |
| P2 | Добавление 50 участников в группу | 50 member_ids | • Операция выполняется атомарно<br>• При ошибке - полный rollback |
| P3 | Создание 20 отделов | 20 departments | • С LDAP: все OU созданы<br>• Без LDAP: только БД |

### 10.2 Нагрузочное тестирование

| ID | Сценарий | Условия | Цель |
|----|----------|---------|------|
| P4 | Concurrent создание пользователей | 10 параллельных запросов | Нет race conditions |
| P5 | Обновление одного пользователя | 5 параллельных PATCH | Последовательность транзакций корректна |

---

## 11. Автоматизация тестирования

### 11.1 Структура тестов

```
tests/
├── test_ldap_optional/
│   ├── __init__.py
│   ├── conftest.py              # Фикстуры для двух режимов
│   ├── test_helpers.py          # Тесты вспомогательных функций
│   ├── test_register.py         # RegisterAPIView
│   ├── test_verify_email.py     # VerifyEmailAPIView
│   ├── test_departments.py      # DepartmentViewSet
│   ├── test_employees.py        # EmployeeViewSet
│   ├── test_positions.py        # PositionViewSet
│   ├── test_groups.py           # GroupViewSet
│   ├── test_integration.py      # Сквозные сценарии
│   └── test_edge_cases.py       # Граничные условия
```

### 11.2 Фикстуры pytest

```python
# conftest.py
import pytest
from django.conf import settings

@pytest.fixture(params=[True, False], ids=["with_ldap", "without_ldap"])
def ldap_mode(request, settings):
    """Параметризованная фикстура для тестирования обоих режимов"""
    original_value = getattr(settings, 'LDAP_ENABLED', False)
    settings.LDAP_ENABLED = request.param
    yield request.param
    settings.LDAP_ENABLED = original_value

@pytest.fixture
def with_ldap(settings):
    """Фикстура для тестов только с LDAP"""
    settings.LDAP_ENABLED = True
    yield
    settings.LDAP_ENABLED = False

@pytest.fixture
def without_ldap(settings):
    """Фикстура для тестов только без LDAP"""
    settings.LDAP_ENABLED = False
    yield

@pytest.fixture
def test_user_data():
    """Базовые данные для создания тестового пользователя"""
    return {
        "email": "test@example.com",
        "first_name": "Test",
        "last_name": "User",
        "phone_number": "+79001234567",
        "password": "SecurePass123!",
        "whatsapp": "+79001234567"
    }
```

### 11.3 Примеры тестов

```python
# test_register.py
import pytest
from rest_framework.test import APIClient
from employees.models import Employee

@pytest.mark.django_db
class TestRegisterAPIView:
    
    def test_register_user_both_modes(self, ldap_mode, test_user_data):
        """R1, R7: Регистрация в обоих режимах"""
        client = APIClient()
        response = client.post('/api/v1/register/', test_user_data)
        
        assert response.status_code == 201
        user = Employee.objects.get(email=test_user_data['email'])
        assert user.is_active is False
        
        if ldap_mode:  # LDAP_ENABLED=True
            assert not user.has_usable_password()  # Пароль в LDAP
            # Проверка создания в LDAP
            from employees.ldap.services import DirectoryService
            svc = DirectoryService()
            ldap_user = svc.get_user_by_email(test_user_data['email'])
            assert ldap_user is not None
        else:  # LDAP_ENABLED=False
            assert user.has_usable_password()  # Пароль в БД
            assert user.check_password(test_user_data['password'])
    
    def test_register_with_avatar_with_ldap(self, with_ldap, test_user_data):
        """R2: Регистрация с аватаром (LDAP)"""
        client = APIClient()
        with open('test_files/avatar.jpg', 'rb') as avatar:
            test_user_data['avatar'] = avatar
            response = client.post('/api/v1/register/', test_user_data, format='multipart')
        
        assert response.status_code == 201
        user = Employee.objects.get(email=test_user_data['email'])
        assert user.avatar  # Аватар сохранён
    
    def test_register_duplicate_email(self, ldap_mode, test_user_data):
        """R3, R9: Дублирование email"""
        client = APIClient()
        Employee.objects.create_user(**test_user_data)
        
        response = client.post('/api/v1/register/', test_user_data)
        assert response.status_code == 400
```

```python
# test_groups.py
import pytest
from rest_framework.test import APIClient
from django.contrib.auth.models import Group

@pytest.mark.django_db
class TestGroupViewSet:
    
    def test_create_group_both_modes(self, ldap_mode, admin_user):
        """G1, G5: Создание группы"""
        client = APIClient()
        client.force_authenticate(user=admin_user)
        
        data = {"name": "TestGroup", "ldap_description": "Test description"}
        response = client.post('/api/v1/groups/', data)
        
        assert response.status_code == 201
        group = Group.objects.get(name="TestGroup")
        assert group is not None
        
        if ldap_mode:
            # Проверка создания в LDAP
            from employees.ldap.services import DirectoryService
            svc = DirectoryService()
            dn = svc.group_find_dn("TestGroup")
            assert dn is not None
    
    def test_add_members_both_modes(self, ldap_mode, admin_user, test_group, test_users):
        """G17, G20: Добавление участников"""
        client = APIClient()
        client.force_authenticate(user=admin_user)
        
        member_ids = [u.id for u in test_users[:3]]
        response = client.post(
            f'/api/v1/groups/{test_group.id}/add-members/',
            {"member_ids": member_ids}
        )
        
        assert response.status_code == 200
        assert test_group.user_set.count() == 3
        
        if ldap_mode:
            # Проверка в LDAP
            from employees.ldap.services import DirectoryService
            svc = DirectoryService()
            dn = svc.group_find_dn(test_group.name)
            members = svc.group_list_members(dn)
            assert len(members) == 3
```

### 11.4 Команды для запуска тестов

```bash
# Все тесты в обоих режимах
pytest tests/test_ldap_optional/ -v

# Только тесты с LDAP
pytest tests/test_ldap_optional/ -v -k "with_ldap"

# Только тесты без LDAP
pytest tests/test_ldap_optional/ -v -k "without_ldap"

# Конкретный тестовый файл
pytest tests/test_ldap_optional/test_register.py -v

# С покрытием кода
pytest tests/test_ldap_optional/ --cov=api.v1.employees.views --cov-report=html

# Параллельный запуск (быстрее)
pytest tests/test_ldap_optional/ -v -n auto
```

---

## 12. Ручное тестирование

### 12.1 Чек-лист для ручной проверки

#### Подготовка
- [ ] Создать .env файл с LDAP_ENABLED=true
- [ ] Создать .env файл с LDAP_ENABLED=false
- [ ] Поднять LDAP сервер (для режима с LDAP)
- [ ] Запустить миграции БД

#### Регистрация и верификация
- [ ] Зарегистрировать пользователя с LDAP
- [ ] Зарегистрировать пользователя без LDAP
- [ ] Верифицировать email в обоих режимах
- [ ] Попытаться войти после верификации

#### Отделы
- [ ] Создать отдел с LDAP
- [ ] Создать отдел без LDAP
- [ ] Добавить участника в отдел (оба режима)
- [ ] Удалить участника из отдела (оба режима)
- [ ] Назначить роль участнику (оба режима)
- [ ] Удалить отдел (оба режима)

#### Сотрудники
- [ ] Создать сотрудника через админ-панель (оба режима)
- [ ] Обновить имя/email/телефон (оба режима)
- [ ] Назначить позицию (оба режима)
- [ ] Загрузить аватар (оба режима)

#### Позиции
- [ ] Создать позицию (оба режима)
- [ ] Назначить группы позиции (оба режима)
- [ ] Удалить позицию (оба режима)

#### Группы
- [ ] Создать группу (оба режима)
- [ ] Переименовать группу (оба режима)
- [ ] Добавить участников в группу (оба режима)
- [ ] Удалить участников из группы (оба режима)
- [ ] Удалить группу (оба режима)

### 12.2 Инструменты для ручного тестирования

**Postman Collection:**
- Импортировать коллекцию API endpoints
- Создать окружения для LDAP/No-LDAP
- Выполнить последовательность запросов

**LDAP Browser (для режима с LDAP):**
- Apache Directory Studio
- JXplorer
- Проверка структуры OU, пользователей, групп

**Django Admin:**
- Проверка записей в БД
- Сравнение с LDAP (в режиме с LDAP)

---

## 13. Критерии успешности тестирования

### 13.1 Обязательные критерии (PASS/FAIL)

✅ **PASS критерии:**
1. Все автоматические тесты проходят в обоих режимах (≥95% успешности)
2. Нет критических ошибок (500) при корректных запросах
3. Данные в БД консистентны после всех операций
4. В режиме с LDAP: данные синхронизированы между LDAP и БД
5. В режиме без LDAP: все операции работают без вызовов DirectoryService
6. Rollback механизмы работают корректно при ошибках
7. Аутентификация работает в обоих режимах

### 13.2 Метрики качества

| Метрика | Целевое значение |
|---------|------------------|
| Покрытие кода тестами | ≥ 90% |
| Успешность автотестов | 100% |
| Время выполнения всех тестов | < 5 минут |
| Количество критических багов | 0 |
| Количество major багов | ≤ 2 |
| Производительность (регистрация с LDAP) | < 3s на пользователя |
| Производительность (регистрация без LDAP) | < 1s на пользователя |

### 13.3 Тест-репорт

После завершения тестирования создать отчёт:

```markdown
# Отчёт о тестировании LDAP Optional Integration

## Окружение
- Django версия: X.X.X
- Python версия: X.X.X
- LDAP сервер: OpenLDAP X.X.X / AD

## Результаты автотестов
- Всего тестов: XXX
- Успешно: XXX (XX%)
- Провалено: XX (XX%)
- Пропущено: XX

## Покрытие кода
- Общее: XX%
- views.py: XX%

## Найденные баги
1. [CRITICAL] Описание бага...
2. [MAJOR] Описание бага...

## Рекомендации
- Улучшение 1...
- Улучшение 2...

## Заключение
✅ Система готова к развёртыванию / ❌ Требуется доработка
```

---

## 14. Continuous Integration (CI)

### 14.1 GitHub Actions / GitLab CI

```yaml
# .github/workflows/test_ldap_optional.yml
name: Test LDAP Optional Integration

on: [push, pull_request]

jobs:
  test-with-ldap:
    runs-on: ubuntu-latest
    services:
      ldap:
        image: osixia/openldap:latest
        ports:
          - 389:389
        env:
          LDAP_ORGANISATION: "Test Org"
          LDAP_DOMAIN: "example.com"
          LDAP_ADMIN_PASSWORD: "admin"
    
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      - name: Run tests with LDAP
        env:
          LDAP_ENABLED: true
          LDAP_SERVER_URI: ldap://localhost:389
        run: |
          pytest tests/test_ldap_optional/ -v -k "with_ldap"
  
  test-without-ldap:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      - name: Run tests without LDAP
        env:
          LDAP_ENABLED: false
        run: |
          pytest tests/test_ldap_optional/ -v -k "without_ldap"
```

---

## 15. Заключение

Этот план тестирования обеспечивает:

1. **Полноту покрытия** - все 50+ методов во всех ViewSets
2. **Двойное тестирование** - каждая функция в обоих режимах
3. **Автоматизацию** - pytest тесты для CI/CD
4. **Документированность** - четкие test case ID и ожидаемые результаты
5. **Воспроизводимость** - фикстуры и примеры кода
6. **Масштабируемость** - легко добавить новые тест-кейсы

**Следующие шаги:**
1. Реализовать базовые автотесты (conftest.py, test_helpers.py)
2. Постепенно покрыть каждый ViewSet тестами
3. Настроить CI для автоматического прогона
4. Провести ручное тестирование по чек-листу
5. Исправить найденные баги
6. Создать итоговый отчёт
