"use client";

import { useMemo } from "react";
import {
  FileText,
  Upload,
  Clock,
  Star,
  TrendingUp,
  Users,
  CheckCircle2,
  FileCheck,
} from "lucide-react";
import {
  BarChart,
  Bar,
  PieChart,
  Pie,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell,
} from "recharts";

export interface DashboardStats {
  totalDocuments: number;
  documentsByType: Array<{ type: string; count: number }>;
  documentsByStatus: Array<{ status: string; count: number }>;
  uploadsOverTime: Array<{ date: string; count: number }>;
  myDocuments: number;
  recentActivity: Array<{
    id: number;
    type: "upload" | "status_change" | "edit" | "view";
    document: string;
    user: string;
    timestamp: string;
  }>;
}

interface DocumentsDashboardProps {
  stats: DashboardStats;
  recentDocuments?: Array<{
    id: number;
    title: string;
    type?: string;
    uploaded_at: string;
    uploaded_by?: string;
  }>;
  favoriteDocuments?: Array<{
    id: number;
    title: string;
    type?: string;
  }>;
  myDocuments?: Array<{
    id: number;
    title: string;
    uploaded_at: string;
  }>;
}

const COLORS = ["#0ea5e9", "#06b6d4", "#14b8a6", "#10b981", "#84cc16", "#eab308", "#f59e0b"];

const ACTIVITY_ICONS = {
  upload: Upload,
  status_change: RefreshCw,
  edit: FileCheck,
  view: Clock,
};

const ACTIVITY_LABELS = {
  upload: "загрузил",
  status_change: "изменил статус",
  edit: "отредактировал",
  view: "просмотрел",
};

function RefreshCw(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      <path d="M21 2v6h-6" />
      <path d="M3 12a9 9 0 0 1 15-6.7L21 8" />
      <path d="M3 22v-6h6" />
      <path d="M21 12a9 9 0 0 1-15 6.7L3 16" />
    </svg>
  );
}

export function DocumentsDashboard({
  stats,
  recentDocuments = [],
  favoriteDocuments = [],
  myDocuments = [],
}: DocumentsDashboardProps) {
  // Подготовка данных для графиков
  const typeChartData = useMemo(() => {
    return stats.documentsByType.map((item, index) => ({
      ...item,
      color: COLORS[index % COLORS.length],
    }));
  }, [stats.documentsByType]);

  const statusChartData = useMemo(() => {
    return stats.documentsByStatus.map((item, index) => ({
      ...item,
      color: COLORS[index % COLORS.length],
    }));
  }, [stats.documentsByStatus]);

  return (
    <div className="space-y-6">
      {/* Статистика - карточки */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        {/* Всего документов */}
        <div className="app-surface rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="app-text-muted text-sm">Всего документов</p>
              <p className="mt-1 text-2xl font-bold text-[var(--foreground)]">{stats.totalDocuments}</p>
            </div>
            <div className="app-selected app-accent-text rounded-full p-3">
              <FileText size={24} />
            </div>
          </div>
        </div>

        {/* Мои документы */}
        <div className="app-surface rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="app-text-muted text-sm">Мои документы</p>
              <p className="mt-1 text-2xl font-bold text-[var(--foreground)]">{stats.myDocuments}</p>
            </div>
            <div className="app-feedback-success rounded-full p-3">
              <Users size={24} />
            </div>
          </div>
        </div>

        {/* Активность */}
        <div className="app-surface rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="app-text-muted text-sm">Активность (7 дней)</p>
              <p className="mt-1 text-2xl font-bold text-[var(--foreground)]">
                {stats.uploadsOverTime.slice(-7).reduce((sum, item) => sum + item.count, 0)}
              </p>
            </div>
            <div className="app-selected app-accent-text rounded-full p-3">
              <TrendingUp size={24} />
            </div>
          </div>
        </div>
      </div>

      {/* Графики */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* График загрузок по времени */}
        <div className="app-surface rounded-lg p-4">
          <h3 className="mb-4 text-base font-semibold text-[var(--foreground)]">
            Загрузки за последние 30 дней
          </h3>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={stats.uploadsOverTime.slice(-30)}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 12 }}
                tickFormatter={(value) => {
                  const date = new Date(value);
                  return `${date.getDate()}.${date.getMonth() + 1}`;
                }}
              />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip
                labelFormatter={(value) => new Date(value).toLocaleDateString("ru-RU")}
              />
              <Line
                type="monotone"
                dataKey="count"
                stroke="#0ea5e9"
                strokeWidth={2}
                dot={{ fill: "#0ea5e9" }}
                name="Документы"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Распределение по типам */}
        <div className="app-surface rounded-lg p-4">
          <h3 className="mb-4 text-base font-semibold text-[var(--foreground)]">
            Распределение по типам
          </h3>
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie
                data={typeChartData}
                dataKey="count"
                nameKey="type"
                cx="50%"
                cy="50%"
                outerRadius={80}
                label
              >
                {typeChartData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Распределение по статусам */}
        <div className="app-surface rounded-lg p-4">
          <h3 className="mb-4 text-base font-semibold text-[var(--foreground)]">
            Распределение по статусам
          </h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={statusChartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="status" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey="count" name="Документы">
                {statusChartData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Лента активности */}
        <div className="app-surface rounded-lg p-4">
          <h3 className="mb-4 text-base font-semibold text-[var(--foreground)]">Последняя активность</h3>
          <div className="space-y-3">
            {stats.recentActivity.slice(0, 5).map((activity) => {
              const Icon = ACTIVITY_ICONS[activity.type];
              return (
                <div key={activity.id} className="flex items-start gap-3 text-sm">
                  <div className="app-surface-muted mt-0.5 rounded-full p-1.5">
                    <Icon size={14} className="app-text-muted" />
                  </div>
                  <div className="flex-1">
                    <p className="text-[var(--foreground)]">
                      <span className="font-medium">{activity.user}</span>{" "}
                      {ACTIVITY_LABELS[activity.type]}{" "}
                      <span className="font-medium">{activity.document}</span>
                    </p>
                    <p className="app-text-muted text-xs">
                      {new Date(activity.timestamp).toLocaleString("ru-RU")}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Секции документов */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Недавние документы */}
        <div className="app-surface rounded-lg p-4">
          <div className="mb-3 flex items-center gap-2">
            <Clock size={16} className="app-text-muted" />
            <h3 className="text-sm font-semibold text-[var(--foreground)]">Недавние</h3>
          </div>
          <div className="space-y-2">
            {recentDocuments.slice(0, 5).map((doc) => (
              <div
                key={doc.id}
                className="app-surface-muted rounded p-2 hover:border-[color:var(--accent-primary)] hover:bg-[color:var(--accent-soft)]"
              >
                <p className="truncate text-sm font-medium text-[var(--foreground)]">{doc.title}</p>
                <p className="app-text-muted text-xs">
                  {doc.type && <span className="mr-2">📄 {doc.type}</span>}
                  {new Date(doc.uploaded_at).toLocaleDateString("ru-RU")}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Избранные документы */}
        <div className="app-surface rounded-lg p-4">
          <div className="mb-3 flex items-center gap-2">
            <Star size={16} className="app-accent-text" />
            <h3 className="text-sm font-semibold text-[var(--foreground)]">Избранные</h3>
          </div>
          <div className="space-y-2">
            {favoriteDocuments.length > 0 ? (
              favoriteDocuments.slice(0, 5).map((doc) => (
                <div
                  key={doc.id}
                  className="app-surface-muted rounded p-2 hover:border-[color:var(--accent-primary)] hover:bg-[color:var(--accent-soft)]"
                >
                  <p className="truncate text-sm font-medium text-[var(--foreground)]">{doc.title}</p>
                  {doc.type && <p className="app-text-muted text-xs">📄 {doc.type}</p>}
                </div>
              ))
            ) : (
              <p className="app-text-muted text-sm">Нет избранных документов</p>
            )}
          </div>
        </div>

        {/* Мои документы */}
        <div className="app-surface rounded-lg p-4">
          <div className="mb-3 flex items-center gap-2">
            <Users size={16} className="app-text-muted" />
            <h3 className="text-sm font-semibold text-[var(--foreground)]">Мои документы</h3>
          </div>
          <div className="space-y-2">
            {myDocuments.slice(0, 5).map((doc) => (
              <div
                key={doc.id}
                className="app-surface-muted rounded p-2 hover:border-[color:var(--accent-primary)] hover:bg-[color:var(--accent-soft)]"
              >
                <p className="truncate text-sm font-medium text-[var(--foreground)]">{doc.title}</p>
                <p className="app-text-muted text-xs">
                  {new Date(doc.uploaded_at).toLocaleDateString("ru-RU")}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
