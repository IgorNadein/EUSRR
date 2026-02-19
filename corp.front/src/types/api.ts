// Common types
export interface User {
  id: number;
  email: string;
  phone_number?: string;
  first_name: string;
  last_name: string;
  middle_name?: string;
  position?: Position;
  department?: Department;
  avatar?: string;
  is_active: boolean;
  telegram?: string;
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
  chat_type: 'direct' | 'group' | 'department';
  participants: User[];
  last_message?: Message;
  unread_count?: number;
  created_at: string;
}

export interface Message {
  id: number;
  chat: number;
  sender: User;
  content: string;
  is_read: boolean;
  created_at: string;
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
  middle_name?: string;
  telegram?: string;
  whatsapp?: string;
  wechat?: string;
}
