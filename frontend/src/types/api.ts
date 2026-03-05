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
  auth?: {
    id?: number;
    email?: string;
    is_staff?: boolean;
    is_superuser?: boolean;
    groups?: string[];
    permissions?: string[];
    permissions_by_app?: Record<string, string[]>;
  };
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
  author_id?: number;
  type?: 'company' | 'department' | 'employee';
  department?: number | null;
  department_id?: number | null;
  content?: string;
  body?: string;
  title?: string;
  image?: string;
  attachment?: string | null;
  attachment_url?: string | null;
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
  content?: string;
  text?: string;
  image?: string | null;
  attachment?: string | null;
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
  type?: 'vacation' | 'sick_leave' | 'day_off' | 'transfer' | 'dismissal' | 'other';
  request_type?: string;
  display_title?: string;
  description?: string;
  comment?: string;
  status: 'draft' | 'pending' | 'approved' | 'rejected' | 'cancelled' | 'in_progress' | 'completed';
  employee?: User;
  created_by?: User;
  approver?: User;
  assigned_to?: User;
  department?: number | null;
  departments?: number[];
  recipients?: User[];
  cc_users?: User[];
  sent_to_all_department?: boolean;
  recipient_count?: number;
  cc_count?: number;
  is_recipient?: boolean;
  comments_count?: number;
  is_final?: boolean;
  attachment?: string | null;
  attachment_url?: string | null;
  date_from?: string | null;
  date_to?: string | null;
  decided_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface RequestComment {
  id: number;
  request: number;
  author: User;
  text: string;
  created_at: string;
}

// Equipment types
export interface EquipmentCategory {
  id: number;
  name: string;
  description?: string;
}

export interface Equipment {
  id: number;
  name: string;
  description?: string;
  category: number | EquipmentCategory;
  category_name?: string;
  department: number;
  department_name?: string;
  serial_number?: string;
  inventory_number?: string;
  status?: string;
  condition?: string;
  purchase_date: string;
  purchase_cost: string | number;
  assigned_to?: User | number | null;
  assigned_to_details?: User;
  location?: string;
  notes?: string;
  image?: string | null;
  attachment?: string | null;
  attachment_url?: string | null;
  created_by?: User;
  created_at: string;
  updated_at: string;
}

export interface EquipmentComment {
  id: number;
  equipment: number;
  author: User;
  text: string;
  created_at: string;
}

// Procurement Request types
export type ProcurementStatus = 'draft' | 'pending' | 'approved' | 'in_progress' | 'completed' | 'rejected' | 'cancelled';
export type UrgencyLevel = 'low' | 'medium' | 'high' | 'critical';
export type ApprovalStatus = 'pending' | 'approved' | 'rejected';
export type ApprovalRole = 'department_head' | 'finance_manager' | 'director';

export interface ProcurementItem {
  id: number;
  request: number;
  name: string;
  description?: string;
  quantity: string | number;
  unit: string;
  estimated_unit_price: string | number;
  total_price?: string | number;
  supplier_info?: string;
  equipment?: number | null;
}

export interface ProcurementApproval {
  id: number;
  request: number;
  approver: User;
  role: ApprovalRole;
  status: ApprovalStatus;
  comment?: string;
  decided_at?: string | null;
  created_at: string;
}

export interface ProcurementRequest {
  id: number;
  title: string;
  description: string;
  department: number;
  department_name?: string;
  department_details?: Department;
  requestor: User;
  executor?: User | null;
  status: ProcurementStatus;
  urgency: UrgencyLevel;
  items?: ProcurementItem[];
  approvals?: ProcurementApproval[];
  required_approvals?: ApprovalRole[];
  actual_cost?: string | number | null;
  is_editable?: boolean;
  budget_available?: boolean;
  total_estimated_cost?: string | number;
  created_at: string;
  updated_at: string;
}

// Communications types
export interface Chat {
  id: number;
  name?: string;
  avatar?: string | null;
  interlocutor?: { id: number; name?: string; avatar?: string | null } | null;
  chat_type?: 'direct' | 'group' | 'department';
  type?: 'private' | 'group' | 'department' | 'announcement';
  participants?: Array<User | number>;
  participant_names?: string[];
  participant_details?: Array<{ id: number; name?: string; avatar?: string | null }>;
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
  reply_to_id?: number;
  reply_to?: number | Message | null;
  reply_to_message?: Message | null;
  reactions_summary?: Record<string, {
    count: number;
    users?: number[];
    user_names?: string[];
  }>;
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

// Calendar types (django-scheduler)
export interface CalendarEvent {
  id: number;
  title: string;
  description?: string;
  start: string; // django-scheduler использует start/end (не start_time/end_time)
  end: string;
  calendar: number;
  calendar_name?: string;
  color_event?: string;
  rule?: number | null;
  rule_description?: string | null;
  creator?: number | null;
  created_on?: string;
  updated_on?: string;
}

export interface Calendar {
  id: number;
  name: string; // django-scheduler использует name (не title)
  slug: string;
  events_count?: number;
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

// Search types (django-watson)
export type SearchModelType = 'post' | 'employee' | 'department' | 'request' | 'chat' | 'message' | 'event' | 'schedule_event' | 'procurement_request' | 'equipment' | 'document' | 'notification';

export interface SearchResult {
  model_name: SearchModelType;
  object_id: number;
  title: string;
  description?: string;
  url: string;
  meta?: Record<string, any>;
}

export interface SearchResponse {
  query: string;
  results: SearchResult[];
  counts: Record<SearchModelType, number>;
  total: number;
}
