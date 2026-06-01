"use client";

import { useState, useCallback } from "react";
import { ChevronRight, ChevronDown, Folder, FolderOpen, Plus, Edit2, Trash2 } from "lucide-react";

export interface FolderNode {
  id: number;
  name: string;
  parent_id: number | null;
  path: string;
  document_count?: number;
  children?: FolderNode[];
}

interface FolderTreeProps {
  folders: FolderNode[];
  selectedFolderId: number | null;
  onSelectFolder: (folderId: number | null) => void;
  onCreateFolder?: (parentId: number | null) => void;
  onEditFolder?: (folderId: number) => void;
  onDeleteFolder?: (folderId: number) => void;
}

export function FolderTree({
  folders,
  selectedFolderId,
  onSelectFolder,
  onCreateFolder,
  onEditFolder,
  onDeleteFolder,
}: FolderTreeProps) {
  const [collapsedIds, setCollapsedIds] = useState<Set<number>>(new Set());
  const [hoveredId, setHoveredId] = useState<number | null>(null);

  // Построение дерева из плоского списка
  const buildTree = useCallback((flatFolders: FolderNode[]): FolderNode[] => {
    const map = new Map<number | null, FolderNode[]>();
    
    flatFolders.forEach((folder) => {
      const parentId = folder.parent_id;
      if (!map.has(parentId)) {
        map.set(parentId, []);
      }
      map.get(parentId)!.push({ ...folder });
    });

    const attachChildren = (node: FolderNode) => {
      const children = map.get(node.id) || [];
      if (children.length > 0) {
        node.children = children;
        children.forEach(attachChildren);
      }
    };

    const rootNodes = map.get(null) || [];
    rootNodes.forEach(attachChildren);
    
    return rootNodes;
  }, []);

  const tree = buildTree(folders);

  const toggleExpand = (folderId: number) => {
    setCollapsedIds((prev) => {
      const next = new Set(prev);
      if (next.has(folderId)) {
        next.delete(folderId);
      } else {
        next.add(folderId);
      }
      return next;
    });
  };

  const renderNode = (node: FolderNode, level: number = 0) => {
    const isSelected = selectedFolderId === node.id;
    const hasChildren = node.children && node.children.length > 0;
    const isExpanded = Boolean(hasChildren && !collapsedIds.has(node.id));
    const isHovered = hoveredId === node.id;

    return (
      <div key={node.id}>
        <div
          className={`group flex items-center gap-1 rounded-lg px-2 py-1.5 transition ${
            isSelected
              ? "bg-sky-100 text-sky-900"
              : "text-gray-700 hover:bg-gray-100"
          }`}
          style={{ paddingLeft: `${level * 16 + 8}px` }}
          onMouseEnter={() => setHoveredId(node.id)}
          onMouseLeave={() => setHoveredId(null)}
        >
          {/* Expand/Collapse */}
          {hasChildren ? (
            <button
              onClick={() => toggleExpand(node.id)}
              className="shrink-0 rounded p-0.5 hover:bg-gray-200"
            >
              {isExpanded ? (
                <ChevronDown size={14} className="text-gray-500" />
              ) : (
                <ChevronRight size={14} className="text-gray-500" />
              )}
            </button>
          ) : (
            <span className="w-[22px]" />
          )}

          {/* Folder Icon */}
          <button
            onClick={() => onSelectFolder(node.id)}
            className="flex min-w-0 flex-1 items-center gap-2"
          >
            {isExpanded || isSelected ? (
              <FolderOpen size={16} className="shrink-0 text-sky-600" />
            ) : (
              <Folder size={16} className="shrink-0 text-gray-500" />
            )}
            <span className="truncate text-sm font-medium">{node.name}</span>
            {node.document_count !== undefined && node.document_count > 0 && (
              <span className="ml-auto shrink-0 rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
                {node.document_count}
              </span>
            )}
          </button>

          {/* Actions */}
          {isHovered && (
            <div className="ml-auto flex shrink-0 gap-0.5 opacity-0 group-hover:opacity-100">
              {onCreateFolder && (
                <button
                  onClick={() => onCreateFolder(node.id)}
                  className="rounded p-1 hover:bg-gray-200"
                  title="Создать подпапку"
                >
                  <Plus size={12} className="text-gray-600" />
                </button>
              )}
              {onEditFolder && (
                <button
                  onClick={() => onEditFolder(node.id)}
                  className="rounded p-1 hover:bg-gray-200"
                  title="Переименовать"
                >
                  <Edit2 size={12} className="text-gray-600" />
                </button>
              )}
              {onDeleteFolder && (
                <button
                  onClick={() => onDeleteFolder(node.id)}
                  className="rounded p-1 hover:bg-red-100"
                  title="Удалить"
                >
                  <Trash2 size={12} className="text-red-600" />
                </button>
              )}
            </div>
          )}
        </div>

        {/* Children */}
        {hasChildren && isExpanded && (
          <div>{node.children!.map((child) => renderNode(child, level + 1))}</div>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-1">
      {/* Root folder */}
      <div
        className={`flex items-center gap-2 rounded-lg px-2 py-1.5 transition ${
          selectedFolderId === null
            ? "bg-sky-100 text-sky-900"
            : "text-gray-700 hover:bg-gray-100"
        }`}
      >
        <button
          onClick={() => onSelectFolder(null)}
          className="flex min-w-0 flex-1 items-center gap-2"
        >
          <Folder size={16} className="shrink-0 text-gray-500" />
          <span className="text-sm font-medium">Все документы</span>
        </button>
        {onCreateFolder && (
          <button
            onClick={() => onCreateFolder(null)}
            className="shrink-0 rounded p-1 hover:bg-gray-200"
            title="Создать папку"
          >
            <Plus size={12} className="text-gray-600" />
          </button>
        )}
      </div>

      {/* Tree nodes */}
      {tree.map((node) => renderNode(node))}

      {/* Empty state */}
      {folders.length === 0 && (
        <div className="py-4 text-center text-sm text-gray-500">
          Папок нет
        </div>
      )}
    </div>
  );
}
