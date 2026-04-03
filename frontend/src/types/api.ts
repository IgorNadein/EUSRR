// Common types
export interface Skill {
  id: number;
  name: string;
  description?: string;
}

export interface EmployeeAction {
  id: number;
  employee: number;
  action: string;
  action_display?: string;
  date: string;
  date_display?: string;
  comment?: string;
  extra?: Record<string, any>;
  history?: any;
  created_at?: string;
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
  is_active: boolean; // ВАЖНО: активный сотрудник (не уволен), НЕ онлайн статус!
  telegram?: string;
  whatsapp?: string;
  wechat?: string;
  gender?: string | number; // 1 - мужской, 2 - женский, 0 - не указан
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
export interface DocumentAcknowledgement {
  id: number;
  document: number;
  user: User;
  acknowledged_at: string;
}

export interface Document {
  id: number;
  title: string;
  description?: string;
  file?: string;
  file_url?: string;
  file_name?: string;
  file_size?: number;
  folder?: {
    id: number;
    name: string;
  };
  folder_path?: string;
  tags?: {
    id: number;
    name: string;
    color?: string;
  }[];
  created_by: User;
  created_at: string;
  updated_at: string;
  uploaded_by?: User;
  uploaded_at?: string;
  modified_by?: User;
  modified_at?: string;
  sent_to_all?: boolean;
  recipients?: User[];
  departments?: { id: number; name: string }[];
  acknowledgements?: DocumentAcknowledgement[];
  acknowledgement_required?: boolean;
  is_acknowledged?: boolean;
}

// Document Comments
export interface DocumentComment {
  id: number;
  document: number;
  author: {
    id: number;
    full_name: string;
    avatar?: string;
  };
  text: string;
  parent?: number;
  created_at: string;
  updated_at: string;
  replies_count: number;
  can_edit: boolean;
  can_delete: boolean;
}

export interface CreateDocumentCommentData {
  document: number;
  text: string;
  parent?: number;
}

// Document Tags
export interface DocumentTag {
  id: number;
  name: string;
  slug: string;
  color?: string;
  created_at: string;
  documents_count: number;
}

export interface CreateDocumentTagData {
  name: string;
  color?: string;
}

// Document Versions (django-reversion)
export interface DocumentVersion {
  id: number;
  revision_id: number;
  version: number;
  created_at: string;
  user: string;
  comment: string;
  changes: Record<string, any>;
}

export interface DocumentActivity {
  id: number;
  timestamp: string;
  user: string;
  action: string;
  description: string;
  related_object?: any;
}

export interface RevertDocumentData {
  version_id: number;
}

// Related Documents
export interface RelatedDocument {
  id: number;
  title: string;
  file_type: string;
  created_at: string;
  uploaded_by: string;
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
  parent?: number | null;
  description?: string;
  icon?: string;
  full_path?: string;
  children_count?: number;
  created_at?: string;
  children?: EquipmentCategory[];
}

export interface Equipment {
  id: number;
  name: string;
  inventory_number?: string;
  serial_number?: string;
  category: number;
  category_name?: string;
  category_icon?: string;
  department: number;
  department_name?: string;
  status?: string;
  status_display?: string;
  responsible_person?: number | null;
  responsible_name?: string;
  location?: string;
  purchase_date: string;
  purchase_cost: string | number;
  warranty_until?: string | null;
  notes?: string;
  is_under_warranty?: boolean;
  comments_count?: number;
  maintenance_count?: number;
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

export interface EquipmentCreateOptions {
  allowed_departments: Array<Pick<Department, 'id' | 'name'>>;
  can_choose_department: boolean;
  can_choose_responsible: boolean;
  default_responsible: { id: number; name: string } | null;
  permission_level: 'full' | 'dept_head' | 'scoped' | null;
}

export interface EquipmentTransferHistoryEntry {
  id: number;
  from_department: string | null;
  to_department: string | null;
  from_person: string | null;
  to_person: string | null;
  reason?: string;
  created_by?: string | null;
  date: string;
}

export interface MaintenanceRecord {
  id: number;
  equipment: number;
  equipment_name?: string;
  equipment_inventory?: string;
  date: string;
  type: string;
  type_display?: string;
  description?: string;
  cost?: string | number | null;
  performed_by?: number;
  performed_by_name?: string;
  next_maintenance_date?: string | null;
  created_at: string;
}

// Procurement Request types
export type ProcurementStatus = 'draft' | 'pending' | 'approved' | 'in_progress' | 'completed' | 'rejected' | 'cancelled';
export type UrgencyLevel = 'low' | 'medium' | 'high' | 'critical';
export type ApprovalStatus = 'pending' | 'approved' | 'rejected';

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
  approver: User | number;
  approver_name?: string;
  priority: number;
  status: ApprovalStatus;
  comment?: string;
  step_label?: string;
  status_display?: string;
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
  requestor: User | number;
  requestor_name?: string;
  requestor_email?: string;
  executor?: User | number | null;
  executor_name?: string | null;
  status: ProcurementStatus;
  status_display?: string;
  urgency: UrgencyLevel;
  urgency_display?: string;
  items?: ProcurementItem[];
  approvals?: ProcurementApproval[];
  required_approval_priorities?: number[];
  actual_cost?: string | number | null;
  is_editable?: boolean;
  total_cost?: string | number;
  total_estimated_cost?: string | number;
  created_at: string;
  updated_at: string;
  submitted_at?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface ProcurementSupplier {
  id: number;
  name: string;
  contact_person?: string;
  phone?: string;
  email?: string;
  address?: string;
  website?: string;
  inn?: string;
  rating?: string | number | null;
  is_active: boolean;
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface ProcurementOverviewStats {
  total_requests: number;
  pending_requests: number;
  approved_this_month: number;
  completed_this_month: number;
  total_spent_this_year: string | number;
  by_status: Record<string, number>;
  by_urgency: Record<string, number>;
}

export interface ProcurementDepartmentStats {
  department_id: number;
  department_name: string;
  total_requests: number;
  completed_requests: number;
  pending_requests: number;
  total_spent: string | number;
}

// Communications types
export interface Chat {
  id: number;
  name?: string;
  avatar?: string | null;
  description?: string | null;
  interlocutor?: { id: number; name?: string; avatar?: string | null } | null;
  chat_type?: 'direct' | 'group' | 'department' | 'global' | 'channel' | 'private' | 'announcement' | 'comments';
  type?: 'private' | 'group' | 'department' | 'announcement' | 'global' | 'channel' | 'direct' | 'comments';
  participants?: Array<User | number>;
  participant_names?: string[];
  participant_details?: Array<{ id: number; name?: string; avatar?: string | null }>;
  last_message?: Message;
  unread_count?: number;
  created_at: string;
  created_by?: number;
  is_pinned?: boolean;
  notifications_enabled?: boolean;
  can_manage?: boolean;
  can_reply?: boolean;
  include_all_users?: boolean;
  is_main?: boolean;
  is_blocked?: boolean;
  blocked_at?: string | null;
  blocked_by?: number | null;
  flags?: Record<string, any>;
  extra_data?: Record<string, any>;
  context_object_id?: number | null;
  context_type?: string | null;
  context_app?: string | null;
  memberships?: ChatMembership[];
  user_settings?: ChatUserSettings;
  last_read_message_id?: number | null;
}

export interface ChatMembership {
  id: number;
  user: number;
  user_name?: string;
  role: 'admin' | 'moderator' | 'member' | 'guest';
  joined_at: string;
  invited_by?: number | null;
  is_active: boolean;
  left_at?: string | null;
  can_send_messages: boolean;
  can_add_members: boolean;
  can_remove_members: boolean;
  can_pin_messages: boolean;
  can_manage_members?: boolean;
}

export interface ChatUserSettings {
  id?: number;
  is_pinned: boolean;
  pinned_at?: string | null;
  pin_order: number;
  notifications_enabled: boolean;
  custom_name?: string;
  is_hidden: boolean;
}

export interface Message {
  id: number;
  chat?: number;
  local_id?: string | null;
  sender?: User;
  author?: User;
  author_id?: number;
  author_name?: string;
  avatar?: string;
  content: string;
  is_read?: boolean;
  read_count?: number;
  read_by?: MessageReader[];
  send_state?: 'pending' | 'delayed' | 'failed';
  is_optimistic?: boolean;
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

export interface MessageReader {
  id: number;
  name: string;
  avatar?: string;
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
  is_local?: boolean;
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

// Notifications types (v2 API)
export interface Notification {
  id: number;
  // v2 fields
  verb: string;
  description: string;
  unread: boolean;
  timestamp: string;
  action_url?: string;
  data?: Record<string, any>;
  // Optional actor/target
  actor?: {
    type: string;
    id: number;
    str: string;
  };
  target?: {
    type: string;
    id: number;
    str: string;
  };
  // Legacy v1 fields (для обратной совместимости)
  title?: string;
  message?: string;
  short_message?: string;
  notification_type?: string;
  is_read?: boolean;
  created_at?: string;
  link?: string;
  category?: string; // verb alias для фильтрации
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
  birth_date: string; // YYYY-MM-DD
  gender: 1 | 2; // 1 - мужской, 2 - женский
  avatar: string; // base64 image
  patronymic?: string;
  telegram?: string;
  whatsapp?: string;
  wechat?: string;
  position?: number;
  skills?: number[];
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
