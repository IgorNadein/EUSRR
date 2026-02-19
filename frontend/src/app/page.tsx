import { Heart, MessageSquare, Search, Star } from "lucide-react";
import { AppShell } from "../components/AppShell";

const feedItems = [
  {
    id: 1,
    author: "Алексей Пономарёв",
    time: "2 часа назад",
    text: "Обновил подборку треков для фокуса. Делюсь плейлистом, если тоже любите работать под легкий электро." ,
    tags: ["Музыка", "Работа"],
    actions: { likes: 42, comments: 8, saves: 5 },
  },
  {
    id: 2,
    author: "Виктория Зацарина",
    time: "3 часа назад",
    text: "Собрали командой фотографии с последней пробежки в парке. Город оживает, когда выходит солнце." ,
    tags: ["Спорт", "Фото"],
    actions: { likes: 65, comments: 12, saves: 7 },
  },
  {
    id: 3,
    author: "Unity C#",
    time: "5 часов назад",
    text: "Сегодня делимся лучшими гайдами по микроанимациям в интерфейсах. Собрали 7 примеров с кодом и видео." ,
    tags: ["Дизайн", "Guides"],
    actions: { likes: 88, comments: 16, saves: 21 },
  },
];

export default function Home() {
  return (
    <AppShell>
      <div className="flex flex-col gap-3 rounded-2xl bg-white p-5 shadow-sm ring-1 ring-gray-100">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-full bg-sky-400 text-sm font-semibold text-white">КМ</div>
          <div className="relative w-full">
            <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              className="w-full rounded-full border border-gray-200 bg-gray-50 py-2.5 pl-10 pr-4 text-sm text-gray-800 transition focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
              placeholder="Поиск по ленте"
            />
          </div>
        </div>
        <div className="flex flex-wrap gap-2 text-xs text-sky-700">
          <span className="rounded-full bg-sky-50 px-3 py-1">Статья</span>
          <span className="rounded-full bg-sky-50 px-3 py-1">Фото</span>
          <span className="rounded-full bg-sky-50 px-3 py-1">Ссылка</span>
          <span className="rounded-full bg-sky-50 px-3 py-1">Опрос</span>
          <span className="rounded-full bg-sky-50 px-3 py-1">Событие</span>
        </div>
      </div>

      <div className="space-y-4">
        {feedItems.map((item) => (
          <article key={item.id} className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-gray-100">
            <header className="mb-3 flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-sky-400 text-sm font-semibold text-white">
                  {item.author[0]}
                </div>
                <div>
                  <p className="text-sm font-semibold text-gray-900">{item.author}</p>
                  <p className="text-xs text-gray-500">{item.time}</p>
                </div>
              </div>
            </header>
            <p className="text-sm leading-6 text-gray-800">{item.text}</p>
            <div className="mt-3 flex flex-wrap gap-2 text-xs text-sky-700">
              {item.tags.map((tag) => (
                <span key={tag} className="rounded-full bg-sky-50 px-3 py-1">
                  {tag}
                </span>
              ))}
            </div>
            <div className="mt-4 flex items-center gap-4 text-sm text-gray-600">
              <button className="flex items-center gap-2 rounded-lg px-3 py-2 hover:bg-gray-50">
                <Heart size={16} className="text-gray-400" /> {item.actions.likes}
              </button>
              <button className="flex items-center gap-2 rounded-lg px-3 py-2 hover:bg-gray-50">
                <MessageSquare size={16} className="text-gray-400" /> {item.actions.comments}
              </button>
              <button className="flex items-center gap-2 rounded-lg px-3 py-2 hover:bg-gray-50">
                <Star size={16} className="text-gray-400" /> {item.actions.saves}
              </button>
            </div>
          </article>
        ))}
      </div>
    </AppShell>
  );
}
