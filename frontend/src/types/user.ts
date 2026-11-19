export type UserRole = 
  | 'business_owner' 
  | 'group_admin' 
  | 'group_member' 
  | 'warned_user' 
  | 'bot_owner'
  | 'business_contact';

export type UserStatus = 'online' | 'active' | 'idle' | 'warning' | 'restricted';

export type FeatureStatus = 'active' | 'configured' | 'warning' | 'restricted' | 'inactive' | 'disabled';

export interface FeatureMetric {
  label: string;
  value: string | number;
}

export interface BotFeatureUsage {
  id: string;
  name: string;
  category: 'personal-autoreply' | 'group-management' | 'moderation' | 'general';
  iconName: string;
  status: FeatureStatus;
  statusLabel: string;
  description: string;
  configDetails: Record<string, string | number | boolean>;
  metrics?: FeatureMetric[];
}

export interface UserActivity {
  id: string;
  timestamp: string;
  action: string;
  category: 'business' | 'moderation' | 'group' | 'security' | 'system';
  details: string;
}

export interface BotUser {
  id: string;
  telegramId: number;
  firstName: string;
  lastName?: string;
  username?: string;
  role: UserRole;
  roleLabel: string;
  avatarGradient: string;
  status: UserStatus;
  connectedAt: string;
  lastActive: string;
  associatedChat?: {
    id: number;
    title: string;
    type: string;
  };
  gcName?: string;
  gcId?: number;
  gcType?: string;
  channelName?: string;
  channelId?: number;
  associatedGC?: {
    id: number;
    title: string;
    type: string;
  };
  associatedChannel?: {
    id: number;
    title: string;
    type: string;
  };
  stats: {
    totalInteractions: number;
    autoRepliesSent?: number;
    warningsCount?: number;
    messagesChecked?: number;
    groupsCount?: number;
  };
  featuresUsed: BotFeatureUsage[];
  recentActivity: UserActivity[];
}

export interface BotGroupChat {
  id: string;
  chatId: number;
  title: string;
  type: 'group' | 'supergroup';
  memberCount: number;
  isActive: boolean;
  avatarGradient: string;
  addedAt: string;
  featuresUsed: BotFeatureUsage[];
  stats: {
    messagesChecked: number;
    abuseDeleted?: number;
    linksDeleted: number;
    spamDeleted: number;
    warningsIssued: number;
    usersRestricted: number;
  };
  recentActivity: UserActivity[];
}

export interface BotChannel {
  id: string;
  channelId: number;
  title: string;
  type: 'channel';
  subscriberCount?: number;
  isActive: boolean;
  avatarGradient: string;
  addedAt: string;
  featuresUsed: BotFeatureUsage[];
  stats: {
    postsProcessed: number;
    linksFiltered: number;
  };
  recentActivity: UserActivity[];
}
