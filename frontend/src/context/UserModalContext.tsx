'use client';

import React, { createContext, useContext, useState, ReactNode } from 'react';
import { BotUser, BotGroupChat, BotChannel } from '@/types/user';
import UserDetailModal from '@/components/UserDetailModal';

export type AnyBotEntity = BotUser | BotGroupChat | BotChannel;

interface UserModalContextType {
  selectedEntity: AnyBotEntity | null;
  isOpen: boolean;
  openUserModal: (entity: AnyBotEntity) => void;
  closeUserModal: () => void;
}

const UserModalContext = createContext<UserModalContextType | undefined>(undefined);

export function UserModalProvider({ children }: { children: ReactNode }) {
  const [selectedEntity, setSelectedEntity] = useState<AnyBotEntity | null>(null);
  const [isOpen, setIsOpen] = useState(false);

  const openUserModal = (entity: AnyBotEntity) => {
    setSelectedEntity(entity);
    setIsOpen(true);
  };

  const closeUserModal = () => {
    setIsOpen(false);
  };

  return (
    <UserModalContext.Provider
      value={{
        selectedEntity,
        isOpen,
        openUserModal,
        closeUserModal,
      }}
    >
      {children}
      <UserDetailModal
        entity={selectedEntity}
        isOpen={isOpen}
        onClose={closeUserModal}
      />
    </UserModalContext.Provider>
  );
}

export function useUserModal() {
  const context = useContext(UserModalContext);
  if (!context) {
    throw new Error('useUserModal must be used within a UserModalProvider');
  }
  return context;
}
