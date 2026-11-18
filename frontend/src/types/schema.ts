/**
 * MongoDB Data Models & Schema Interfaces for Waguri Bot Frontend
 */

export interface PromotionItem {
  id: number;
  title: string;
  message: string;
  link_url?: string | null;
  button_text?: string | null;
  target_type: 'all_gc' | 'selected';
  target_chat_ids?: string | null;
  schedule_type: 'once' | 'recurring';
  scheduled_time: string;
  repeat_interval: string;
  status: 'active' | 'paused' | 'completed';
  total_delivered: number;
  last_sent_at?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface PromotionLog {
  id: number;
  promotion_id?: number;
  chat_id: number;
  chat_title: string;
  sent_at: string;
  status: string;
  details?: string;
}

export interface StickerItem {
  id: number;
  chat_id: number;
  chat_title: string;
  sticker_url: string;
  sticker_name: string;
  target_type?: 'single' | 'all_gc' | 'selected';
  target_chat_ids?: string | null;
  schedule_type: 'once' | 'recurring';
  scheduled_time: string;
  repeat_interval: string;
  status: 'active' | 'paused' | 'completed';
  last_sent_at?: string | null;
  sticker_pack_name?: string | null;
  current_index?: number;
  created_at?: string;
  updated_at?: string;
}

export interface StickerLog {
  id: number;
  scheduled_id: number;
  chat_id: number;
  chat_title: string;
  sticker_url: string;
  sent_at: string;
  status: string;
  details?: string;
}

export interface ShayariItem {
  id: number;
  category: string;
  content: string;
  author?: string | null;
  language?: string | null;
  media_url?: string | null;
  tags?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface ScheduledShayariItem {
  id: number;
  title: string;
  category: string;
  content_id?: number | null;
  custom_text?: string | null;
  target_type: 'all_gc' | 'selected';
  target_chat_ids?: string | null;
  schedule_type: 'once' | 'recurring';
  scheduled_time: string;
  repeat_interval: string;
  status: 'active' | 'paused' | 'completed';
  total_delivered: number;
  last_sent_at?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface ChatEntity {
  chat_id: number;
  chat_title: string;
  chat_type: 'group' | 'supergroup' | 'channel';
  is_active: number | boolean;
  added_at?: number;
  updated_at?: number;
}

export interface ChatSettings {
  chat_id: number;
  anti_link_enabled: boolean;
  anti_bio_link_enabled: boolean;
  clean_service_enabled: boolean;
  anti_spam_enabled: boolean;
  flood_detection_enabled: boolean;
  flood_threshold_messages: number;
  flood_window_seconds: number;
  warning_system_enabled: boolean;
  auto_restrict_enabled: boolean;
  anti_forward_enabled: boolean;
  anti_join_spam_enabled: boolean;
  anti_bot_enabled: boolean;
  media_restrictions_enabled: boolean;
  allowed_media_types: Record<string, boolean>;
  spam_window_seconds: number;
  warning_limit: number;
  restriction_duration_seconds: number;
  warning_delete_after_seconds: number;
  custom_warning_msg_1?: string | null;
  custom_warning_msg_2?: string | null;
  custom_greeting_msg?: string | null;
  greeting_enabled: boolean;
  raid_mode_enabled: boolean;
}

export interface UserEntity {
  user_id: number;
  connection_id?: string;
  is_enabled: number | boolean;
  can_reply?: number | boolean;
  account_username?: string | null;
  account_first_name?: string | null;
  connected_at?: number;
  updated_at?: number;
}

export interface SystemSettings {
  anti_link_enabled: boolean;
  anti_bio_link_enabled: boolean;
  clean_service_enabled: boolean;
  anti_spam_enabled: boolean;
  flood_detection_enabled: boolean;
  flood_message_limit: number;
  flood_window_seconds: number;
  spam_window_seconds: number;
  spam_warning_limit: number;
  spam_restriction_seconds: number;
  warning_delete_after_seconds: number;
  global_emergency_overrides: Record<string, boolean>;
  abuse_detection_enabled?: boolean;
  abuse_sexual_language?: boolean;
  abuse_general_language?: boolean;
  abuse_hindi_hinglish?: boolean;
  abuse_harassment?: boolean;
  abuse_threats?: boolean;
  abuse_bypass_detection?: boolean;
  abuse_warning_system?: boolean;
  abuse_warning_limit?: number;
  abuse_mute_duration_minutes?: number;
  updated_at?: string;
}

export interface OverviewTelemetry {
  database: {
    engine: string;
    db_name: string;
    status: string;
  };
  overview: {
    total_users: number;
    total_active_chats: number;
    total_group_chats: number;
    total_channels: number;
    total_messages_checked: number;
    links_deleted: number;
    spam_deleted: number;
    warnings_issued: number;
    restrictions_applied: number;
  };
  schedules: {
    promotions: { total: number; active: number };
    stickers: { total: number; active: number };
    shayari: { total_content: number; active_schedules: number };
  };
  server_time: string;
}
