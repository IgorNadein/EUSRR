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
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Всего документов</p>
              <p className="mt-1 text-2xl font-bold text-gray-900">{stats.totalDocuments}</p>
            </div>
            <div className="rounded-full bg-sky-100 p-3">
              <FileText size={24} className="text-sky-600" />
            </div>
          </div>
        </div>

        {/* Мои документы */}
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Мои документы</p>
              <p className="mt-1 text-2xl font-bold text-gray-900">{stats.myDocuments}</p>
            </div>
            <div className="rounded-full bg-green-100 p-3">
              <Users size={24} className="text-green-600" />
            </div>
          </div>
        </div>

        {/* Активность */}
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Активность (7 дней)</p>
              <p className="mt-1 text-2xl font-bold text-gray-900">
                {stats.uploadsOverTime.slice(-7).reduce((sum, item) => sum + item.count, 0)}
              </p>
            </div>
            <div className="rounded-full bg-purple-100 p-3">
              <TrendingUp size={24} className="text-purple-600" />
            </div>
          </div>
        </div>
      </div>

      {/* Графики */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* График загрузок по времени */}
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <h3 className="mb-4 text-base font-semibold text-gray-900">
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
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <h3 className="mb-4 text-base font-semibold text-gray-900">
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
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <h3 className="mb-4 text-base font-semibold text-gray-900">
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
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <h3 className="mb-4 text-base font-semibold text-gray-900">Последняя активность</h3>
          <div className="space-y-3">
            {stats.recentActivity.slice(0, 5).map((activity) => {
              const Icon = ACTIVITY_ICONS[activity.type];
              return (
                <div key={activity.id} className="flex items-start gap-3 text-sm">
                  <div className="mt-0.5 rounded-full bg-gray-100 p-1.5">
                    <Icon size={14} className="text-gray-600" />
                  </div>
                  <div className="flex-1">
                    <p className="text-gray-900">
                      <span className="font-medium">{activity.user}</span>{" "}
                      {ACTIVITY_LABELS[activity.type]}{" "}
                      <span className="font-medium">{activity.document}</span>
                    </p>
                    <p className="text-xs text-gray-500">
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
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <div className="mb-3 flex items-center gap-2">
            <Clock size={16} className="text-gray-600" />
            <h3 className="text-sm font-semibold text-gray-900">Недавние</h3>
          </div>
          <div className="space-y-2">
            {recentDocuments.slice(0, 5).map((doc) => (
              <div
                key={doc.id}
                className="rounded border border-gray-100 p-2 hover:border-sky-300 hover:bg-sky-50"
              >
                <p className="truncate text-sm font-medium text-gray-900">{doc.title}</p>
                <p className="text-xs text-gray-500">
                  {doc.type && <span className="mr-2">📄 {doc.type}</span>}
                  {new Date(doc.uploaded_at).toLocaleDateString("ru-RU")}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Избранные документы */}
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <div className="mb-3 flex items-center gap-2">
            <Star size={16} className="text-amber-500" />
            <h3 className="text-sm font-semibold text-gray-900">Избранные</h3>
          </div>
          <div className="space-y-2">
            {favoriteDocuments.length > 0 ? (
              favoriteDocuments.slice(0, 5).map((doc) => (
                <div
                  key={doc.id}
                  className="rounded border border-gray-100 p-2 hover:border-sky-300 hover:bg-sky-50"
                >
                  <p className="truncate text-sm font-medium text-gray-900">{doc.title}</p>
                  {doc.type && <p className="text-xs text-gray-500">📄 {doc.type}</p>}
                </div>
              ))
            ) : (
              <p className="text-sm text-gray-500">Нет избранных документов</p>
            )}
          </div>
        </div>

        {/* Мои документы */}
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <div className="mb-3 flex items-center gap-2">
            <Users size={16} className="text-gray-600" />
            <h3 className="text-sm font-semibold text-gray-900">Мои документы</h3>
          </div>
          <div className="space-y-2">
            {myDocuments.slice(0, 5).map((doc) => (
              <div
                key={doc.id}
                className="rounded border border-gray-100 p-2 hover:border-sky-300 hover:bg-sky-50"
              >
                <p className="truncate text-sm font-medium text-gray-900">{doc.title}</p>
                <p className="text-xs text-gray-500">
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
