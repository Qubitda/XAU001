export type DefinitionItem = {
  id: string;
  code: string;
  label: string;
  meta: Record<string, unknown>;
  sortOrder: number;
  isActive: boolean;
  isSystem: boolean;
  parentIds?: string[];
  parentCodes?: string[];
  parentLabels?: string[];
};

export type DefinitionUsage = {
  businessDomain: string;
  usagePurpose: string;
  usedInApps: string[];
  usedInScreens: string[];
  bindsToEntity?: string | null;
  valueStrategy: 'code' | 'label' | string;
  parentFilter: boolean;
  dynamicCapable: boolean;
  criticalMeta: string[];
  integrationStatus: 'wired' | 'reference_only' | 'system_fixed' | 'unverified' | string;
  howToAddOption: string;
};

export type DefinitionTable = {
  id: string;
  code: string;
  name: string;
  description: string;
  sortOrder: number;
  isActive: boolean;
  isSystem: boolean;
  parentTableCode?: string | null;
  parentTableName?: string | null;
  childTableCodes?: string[];
  itemCount?: number;
  activeItemCount?: number;
  items?: DefinitionItem[];
  usage?: DefinitionUsage;
};

export type DefinitionsPayload = {
  tables: DefinitionTable[];
  salesChannels: { code: string; label: string; isSystem?: boolean }[];
  systemFixed?: Array<{
    name: string;
    codes: string[];
    reason: string;
    integrationStatus: string;
  }>;
};
