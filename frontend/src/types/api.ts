// Common types
export interface Skill {
  id: number;
  name: string;
  description?: string;
}

export interface EmployeeAction {
  id: number;
  employee: number;
  action_type: string;
  description?: string;
  date: string;
  created_at: string;
}

export interface EmployeeDepartment {
  id: number;
  name: string;
  role_id?: number;
  role_name?: string;
  is_head: boolean;
  via_assignment?: boolean;
}

export interface User {
  id: number;
  email: string;
  phone_number?: string;
  first_name: string;
  last_name: string;
  patronymic?: string; // отчество (было middle_name)
  position?: Position;
  departments?: EmployeeDepartment[]; // массив отделов с ролями (было department)
  avatar?: string;
  is_active: boolean;
  telegram?: string;
  whatsapp?: string;
  wechat?: string;
  gender?: string;
  birth_date?: string;
  skills?: Skill[];
  actions?: EmployeeAction[];
  email_verified?: boolean;
  created_at?: string;
  updated_at?: string;
  last_login?: string;
  date_joined?: string;
  auth?: Record<string, boolean>; // глобальные права пользователя
}

export interface Department {
  id: number;
  name: string;
  description?: string;
  parent?: number;
  head?: User;
  employees_count?: number;
}

export interface Position {
  id: number;
  name: string;
  description?: string;
}

// Feed types
export interface Post {
  id: number;
  author: User;
  content: string;
  image?: string;
  tags?: string[];
  created_at: string;
  updated_at: string;
  likes_count: number;
  comments_count: number;
  is_liked?: boolean;
}

export interface Comment {
  id: number;
  post: number;
  author: User;
  content: string;
  created_at: string;
  updated_at: string;
}

// Documents types
export interface Document {
  id: number;
  title: string;
  description?: string;
  file?: string;
  document_type: string;
  created_by: User;
  created_at: string;
  updated_at: string;
  tags?: string[];
}

// Requests types
export interface Request {
  id: number;
  title: string;
  description: string;
  request_type: string;
  status: 'pending' | 'approved' | 'rejected' | 'in_progress' | 'completed';
  created_by: User;
  assigned_to?: User;
  created_at: string;
  updated_at: string;
}

// Communications types
export interface Chat {
  id: number;
  name?: string;
  avatar?: string | null;
  chat_type?: 'direct' | 'group' | 'department';
  type?: 'private' | 'group' | 'department' | 'announcement';
  participants: User[];
  last_message?: Message;
  unread_count?: number;
  created_at: string;
}

export interface Message {
  id: number;
  chat?: number;
  sender?: User;
  author?: User;
  author_id?: number;
  author_name?: string;
  avatar?: string;
  content: string;
  is_read?: boolean;
  created_at?: string;
  created?: string;
  created_ts?: number;
  is_edited?: boolean;
  is_deleted?: boolean;
  has_attachments?: boolean;
  attachments?: MessageAttachment[];
}

export interface MessageAttachment {
  id: number;
  file_name: string;
  file_type?: string;
  file_url: string;
  file_size?: number;
  mime_type?: string;
  width?: number;
  height?: number;
  thumbnail?: string | null;
}

// Calendar types
export interface CalendarEvent {
  id: number;
  title: string;
  description?: string;
  start_time: string;
  end_time: string;
  location?: string;
  calendar: number;
  participants?: User[];
  created_by: User;
}

export interface Calendar {
  id: number;
  name: string;
  description?: string;
  color?: string;
  is_public: boolean;
  owner: User;
}

// Notifications types
export interface Notification {
  id: number;
  title: string;
  message: string;
  notification_type: string;
  is_read: boolean;
  created_at: string;
  link?: string;
}

// API Response types
export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

// Auth types
export interface LoginCredentials {
  email?: string;
  phone?: string;
  phone_number?: string;
  password: string;
}

export interface LoginResponse {
  access: string;
  refresh: string;
  user: User;
}

export interface RegisterData {
  email: string;
  phone_number: string;
  password: string;
  first_name: string;
  last_name: string;
  patronymic?: string; // было middle_name
  telegram?: string;
  whatsapp?: string;
  wechat?: string;
}
