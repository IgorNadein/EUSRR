import { AppShell, PageHeader } from "../../components/AppShell";

const employees = [
  { id: 1, name: "Константин Макаев", role: "Руководитель проектов", status: "Онлайн", department: "ИТ" },
  { id: 2, name: "Виктория Зацарина", role: "Дизайнер", status: "Недавно", department: "Маркетинг" },
  { id: 3, name: "Алексей Пономарёв", role: "Разработчик", status: "Оффлайн", department: "ИТ" },
  { id: 4, name: "Эдуард Иванов", role: "Директор", status: "Онлайн", department: "Финансы" },
];
export default function EmployeesPage() {
  const sortedEmployees = [...employees].sort((a, b) => a.name.localeCompare(b.name, "ru"));

  return (
    <AppShell>
      <PageHeader title="Сотрудники" eyebrow="Команда" badge={`Всего: ${employees.length}`} />

      <div className="space-y-3">
        {sortedEmployees.map((employee) => {
          const isOnline = employee.status === "Онлайн";
          const statusColor = isOnline ? "text-green-600" : employee.status === "Недавно" ? "text-amber-600" : "text-gray-500";
          const dotColor = isOnline ? "bg-green-500" : employee.status === "Недавно" ? "bg-amber-500" : "bg-gray-400";

          return (
            <article key={employee.id} className="flex items-center gap-4 rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-sky-400 text-sm font-semibold text-white">
                {employee.name
                  .split(" ")
                  .slice(0, 2)
                  .map((part) => part[0])
                  .join("")}
              </div>
              <div className="flex-1">
                <p className="text-sm font-semibold text-gray-900">{employee.name}</p>
                <p className="text-xs text-gray-500">{employee.role}</p>
                <div className="mt-2 flex items-center gap-2 text-xs text-gray-500">
                  <span className={`h-2 w-2 rounded-full ${dotColor}`} />
                  <span className={statusColor}>{employee.status}</span>
                  <span className="mx-1 text-gray-300">•</span>
                  <span className="text-gray-500">{employee.department}</span>
                </div>
              </div>
            </article>
          );
        })}
      </div>
    </AppShell>
  );
}
