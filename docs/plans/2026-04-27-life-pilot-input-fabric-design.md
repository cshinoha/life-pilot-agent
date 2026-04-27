# Life Pilot Input Fabric — план минимально-фрикционного ввода

Дата: 2026-04-27
Статус: продуктовый план для обсуждения; техническая реализация ещё не утверждена

## 1. Проблема

Life Pilot не должен быть только Telegram-ботом. Telegram остаётся полезным каналом, но цель шире: сделать слой ввода, через который любая мысль, голосовая заметка, ссылка, письмо, календарное событие или результат встречи попадает в систему почти без усилия.

Главный принцип:

> Сначала собрать весь input. Затем классифицировать то, что можно классифицировать. Уточнять у пользователя только то, что нельзя классифицировать уверенно.

Это продолжает направление, которое появилось после исследования похожих продуктов и проектов: ClickUp Brain, Notion AI/Agents, Taskade, Limitless, Otter, Fireflies, Routine, Telegram/Todoist/Gmail/Calendar assistants.

Целевой цикл:

```text
мысль / голос / ссылка / письмо / встреча
→ capture
→ классификация
→ структурирование
→ предложенные действия
→ подтверждение / выполнение
```

## 2. Что уже есть в Life Pilot

В текущем Life Pilot уже есть важная часть будущей системы: `/process`.

Он умеет:

- брать записи дня;
- делить их на уверенно классифицированные и неоднозначные;
- уточнять неоднозначные записи через кнопки;
- финализировать результат;
- показывать отчёт;
- давать возможность скорректировать результат;
- делать undo после commit.

Но это пока не универсальная очередь input-а. Сейчас поток примерно такой:

```text
daily note → /process → clarification → finalize
```

Нужный поток шире:

```text
любой источник → capture item → classifier → review only if needed → routing
```

Вывод: не нужно придумывать review-механику с нуля. Нужно обобщить существующий `/process` clarification/correction flow до универсальной очереди захвата и уточнения.

## 3. Продуктовая модель

### 3.1. Capture всё без вопросов

На входе пользователь не должен выбирать тип записи.

Плохо:

```text
“Это задача, мысль, идея или напоминание?”
```

Хорошо:

```text
Пользователь сказал / отправил / поделился → Life Pilot сразу сохранил.
```

Категория определяется позже.

### 3.2. Input должен быть source-agnostic

Система должна принимать input из разных источников:

- Telegram text;
- Telegram voice;
- Telegram photo / file;
- forwarded messages;
- mobile share sheet;
- mobile shortcut;
- desktop hotkey;
- browser selected text / current page;
- email / inbox;
- calendar context;
- meeting transcript;
- drop folder для файлов.

Все источники должны приводиться к одной внутренней сущности: `CaptureItem`.

### 3.3. Классификация делит input на несколько корзин

После capture система должна разделить элементы на:

1. **Classified**
   Система уверенно понимает, что это такое.

2. **Uncertain**
   Есть несколько вероятных вариантов, нужен выбор пользователя.

3. **Unclassifiable**
   Недостаточно информации, нужен уточняющий вопрос.

4. **Noise / ignore candidate**
   Похоже на шум, но лучше не удалять молча.

Пример:

```text
“Позвонить Сергею завтра” → classified: task/reminder
“Интересная мысль про агентность” → classified: note/idea
“Сергей завтра” → unclassifiable: что с этим сделать?
“Вот это надо бы” → uncertain: задача или мысль?
```

### 3.4. Уточнять только неоднозначное

Фрикшн должен появляться не на этапе ввода, а только когда система не уверена.

Правильные вопросы:

- “Это задача, заметка или идея?”
- “Создать задачу, сохранить заметку или проигнорировать?”
- “Это нужно сделать, запомнить или обсудить позже?”
- “Похоже на follow-up после встречи. Создать задачу?”

Неправильные вопросы:

- “Что ты хочешь с этим сделать?” — если можно предложить варианты.
- “Как классифицировать?” — слишком абстрактно.
- “Расскажи подробнее” — только если вариантов действительно недостаточно.

## 4. Рекомендуемый продуктовый подход

### Слой 1 — Universal Capture

Любой источник создаёт capture-запись. Система ничего не теряет и не заставляет пользователя думать о структуре.

### Слой 2 — Classifier

AI классифицирует capture-записи:

- task;
- note / thought;
- idea;
- project candidate;
- reminder;
- follow-up;
- reference / link;
- noise.

### Слой 3 — Clarification Queue

Очередь показывает только то, где нужна помощь пользователя:

- ambiguous classification;
- low confidence;
- missing intent;
- risky action;
- external side effect.

### Слой 4 — Review / Approval

Система предлагает действия пачкой:

- создать задачу;
- сохранить заметку;
- добавить идею;
- создать project candidate;
- создать reminder proposal;
- сохранить ссылку;
- проигнорировать.

### Слой 5 — Routing

После подтверждения элементы уходят в правильные места:

- TaskNotes;
- daily note;
- thoughts;
- project inbox;
- links/reference inbox;
- reminder/calendar proposal.

## 5. Приоритеты input-каналов

### 5.1. Mobile: Telegram + shortcuts/share

Рекомендация: оставить Telegram как базовый mobile channel, но не ограничиваться им.

Почему:

- Telegram уже работает;
- голосовые уже привычны;
- forwarding уже естественный;
- быстро поддержать без отдельного приложения.

Что добавить позже:

- mobile share-to-Life-Pilot;
- quick text shortcut;
- quick voice shortcut;
- возможно PWA capture screen.

### 5.2. Desktop: global hotkey

Рекомендация: desktop hotkey — главный следующий input вне Telegram.

Идеальный UX:

```text
нажал hotkey → сказал/написал → отпустил → Life Pilot сохранил
```

Почему это важно:

- пользователь часто думает за компьютером;
- открывать Telegram — лишний context switch;
- hotkey ближе к Voxtype/Routine/Limitless паттерну;
- это самый сильный способ снизить фрикшн для мыслей “на лету”.

### 5.3. Browser capture

Рекомендация: после hotkey добавить browser capture.

Сценарии:

- сохранить текущую страницу;
- сохранить выделенный текст;
- добавить краткий комментарий к ссылке;
- отправить статью в processing/research queue.

### 5.4. Passive sources

Рекомендация: подключать после появления устойчивой capture/review queue.

Порядок:

1. Calendar — контекст дня, свободные окна, follow-ups.
2. Email / inbox — задачи, ожидания, входящие обязательства.
3. Meeting transcripts — решения, action items, follow-ups.
4. Files/drop folder — документы и вложения.
5. Health/sleep — позже, потому что DPV уже частично покрывает ресурс.

## 6. Что считать MVP

Минимальный полезный MVP:

1. Есть единая capture-очередь.
2. Telegram text/voice попадают в неё без дополнительного действия пользователя.
3. Система классифицирует новые capture-записи.
4. Уверенные элементы получают proposed actions.
5. Неуверенные элементы попадают в clarification queue.
6. Пользователь уточняет только ambiguous/unclassifiable input.
7. Подтверждённые действия маршрутизируются в TaskNotes/daily/thoughts.
8. Старый `/process` продолжает работать, пока новый pipeline не стабилен.

## 7. Что не входит в MVP

- Нативное мобильное приложение.
- Полноценный browser extension.
- Автоматическая обработка email без review.
- Автоматические изменения календаря.
- Clipboard watcher.
- Полный passive/ambient capture.
- Удаление текущего `/process` pipeline.

## 8. Основные риски

### Риск 1 — дублирование задач

Один и тот же input может попасть и в daily note, и в capture queue.

Митигация:

- source id;
- backlink на исходный capture item;
- dedupe перед созданием task;
- сначала mirror-mode, потом миграция.

### Риск 2 — review queue станет ещё одним inbox

Если очередь будет копиться, она станет фрикшном.

Митигация:

- batch review;
- defaults;
- skip all;
- weekly cleanup;
- auto-route low-risk notes/references.

### Риск 3 — слишком много уточнений

Если AI будет часто сомневаться, UX станет раздражающим.

Митигация:

- confidence thresholds;
- learning from user choices;
- правила “если похоже на заметку — сохраняй как заметку, не спрашивай”;
- спрашивать только при потенциальном действии или явной неоднозначности.

### Риск 4 — privacy для passive sources

Email, calendar и meetings могут быть чувствительными.

Митигация:

- explicit opt-in per source;
- local-first raw storage;
- external actions only after approval;
- clear audit trail.

## 9. Решения, которые ещё надо обсудить отдельно

Этот документ фиксирует продуктовый план, но не утверждает техническую реализацию.

Открытые технические вопросы:

1. Где хранить capture queue: JSON files, JSONL, SQLite или markdown?
2. Делать ли отдельный HTTP API для input-каналов сразу или позже?
3. Как именно связать capture items с daily notes, чтобы не было дубликатов?
4. Какие категории считаются safe auto-route?
5. Какие actions всегда требуют approval?
6. Как должен выглядеть `/review` UX в Telegram?
7. Нужен ли отдельный `/inbox`, или достаточно `/review`?
8. Когда и как подключать desktop hotkey?
9. Как хранить learning rules из ответов пользователя?

## 10. Зафиксированное продуктовое решение

Следующая большая фича Life Pilot — **Input Fabric**:

```text
собирать весь input
→ автоматически классифицировать всё очевидное
→ уточнять только неоднозначное
→ предлагать действия
→ маршрутизировать подтверждённое
```

Первый технический шаг должен быть не новый канал ввода, а фундамент:

> Universal Capture Classifier + Clarification Queue

После него можно добавлять mobile shortcuts, desktop hotkey, browser capture и passive sources без переписывания ядра.
