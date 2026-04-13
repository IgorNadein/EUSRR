# Frontend Guide: Developer Workflow

Этот документ отвечает на вопрос: как practically разрабатывать новый UI в этом проекте.

## 1. Порядок работы над новой UI-задачей

Рекомендуемый порядок:

1. понять, это новый паттерн или существующий
2. найти ближайшие shared primitives
3. определить уровень поверхности и геометрии
4. собрать layout из существующих слоёв
5. вынести тяжёлые feature-блоки из page-level файла, если экран уже растёт за счёт list row / detail modal / compose workspace
6. только потом добавлять локальные override

Неправильный порядок:

1. сразу писать JSX с локальными utility-классами
2. потом пытаться “подогнать под проект”

## 2. Как делать новый экран

Перед началом нового экрана:

- определить, это обычная app-page или отдельный auth/legal flow
- понять, нужен ли `AppShell`
- определить основной primary panel
- определить, сколько secondary blocks реально нужно

Практический шаблон:

1. взять `AppShell`, если это обычная страница приложения
2. использовать `PageHeader`, если нужен стандартный page intro
3. построить крупные контейнеры как `app-surface rounded-2xl`
4. вложенные секции делать через `app-surface-muted rounded-xl`
5. поля формы строить на `app-input` / `app-select`

## 3. Как делать новую карточку

Перед созданием карточки спросить:

- это primary container или secondary grouped block?
- карточка реально нужна, или это просто внутренний helper block?
- не создаём ли мы третью глубину вложенности без необходимости?

Норма:

- primary card: `app-surface rounded-2xl`
- secondary card: `app-surface-muted rounded-xl`
- маленький helper: `rounded-lg` или `rounded-xl`, но не новая “мини-основная карточка”

## 4. Как делать новую форму

Сначала определить тип формы:

- CRUD
- compose
- filters
- settings
- dialog action

После этого:

- выбрать подходящий form contract
- использовать общие primitives
- решить, какие поля главные, а какие вторичные
- если compose-форма превращается в workspace, вынести её из page-level JSX в feature component

Важно:

- не все формы должны выглядеть одинаково
- но все формы должны жить в одной визуальной системе
- page-level файл не должен оставаться местом для длинной compose-модалки, если она уже стала отдельным рабочим сценарием

То же правило для list/detail flow:

- если у страницы появились тяжёлые expandable rows, detail modal или participant-heavy blocks, это уже кандидат на feature components, а не на дальнейшее разрастание page-level JSX
- то же касается toolbar/filter block и attachment preview, если они уже стали самостоятельными зонами сценария
- router-sync, deep-link opening и dismissable menu state тоже можно выносить в feature hook, если это screen orchestration, а не данные домена
- если внутри одной зоны уже несколько leaf-компонентов, стоит ввести feature container вроде `*Section` или `*Panel`, а не возвращать всё обратно в page-level JSX
- dense row после такого выноса не должна оставаться одним бесформенным JSX-комком: отдельно собираются action rail, main content и secondary panels вроде details/comments
- если у toolbar/filter block пропсы начинают расползаться, лучше сгруппировать feature-local `state` и `actions`, чем продолжать расширять плоский список `onSet*` и `value`

## 5. Как делать dropdown-поле

Порядок решения:

1. если это простой одиночный выбор без поиска, можно использовать `app-select`
2. если нужен поиск, chips, multi-select или compose-поведение, брать `SearchableSelect*`
3. если хочется “чуть-чуть допилить стрелочку”, сначала проверить, не означает ли это, что нужен shared pattern, а не local fix

Красный флаг:

- локальная стилизация native `select`, чтобы он выглядел как shared dropdown, почти всегда означает неправильный выбор primitive

## 6. Как делать модалку

Если нужен обычный dialog:

- использовать `Modal`

Перед реализацией определить:

- это modal dialog, drawer или workspace?
- нужен ли sticky footer?
- нужна ли длинная scrollable content area?

Нормальный modal workflow:

1. взять `Modal`
2. определить размер
3. собрать shell на `app-surface-elevated`
4. выстроить content hierarchy
5. проверить mobile-скролл и footer actions

## 7. Когда выносить в shared

Выносить в shared, если:

- паттерн повторится минимум ещё раз
- это не доменная логика, а UI-механика
- локальный код начинает превращаться в новый mini-framework внутри страницы

Не выносить рано, если:

- решение ещё сырое
- паттерн пока узкоспецифичный
- компонент завязан на один домен и вряд ли станет общим

## 8. Когда можно делать локальный override

Локальный override допустим, если:

- нет подходящего primitive
- решение реально локально
- не ломается общий visual contract
- override не рождает новый незафиксированный паттерн

Если override начинает повторяться, это уже shared problem, а не local exception.

## 9. Что проверять до завершения работы

Перед тем как считать UI-задачу завершённой, проверить:

- поверхность и радиусы соответствуют guide
- нет лишнего custom radius
- поля используют `app-*` primitives
- dropdown affordance не локально придуман
- mobile layout выглядит естественно
- действия формы и карточки читаются по визуальному весу
- role-based фронтовые эвристики не подменяют API contract там, где источник истины должен приходить с backend
