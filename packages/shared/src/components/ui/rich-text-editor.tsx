import { useEffect, type ReactNode } from 'react';
import { EditorContent, useEditor } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Underline from '@tiptap/extension-underline';
import { TextStyle } from '@tiptap/extension-text-style';
import { Color } from '@tiptap/extension-color';
import Highlight from '@tiptap/extension-highlight';
import Link from '@tiptap/extension-link';
import TextAlign from '@tiptap/extension-text-align';
import Placeholder from '@tiptap/extension-placeholder';
import {
  AlignCenter,
  AlignLeft,
  AlignRight,
  Bold,
  Highlighter,
  Italic,
  Link2,
  List,
  ListOrdered,
  Redo2,
  Strikethrough,
  Underline as UnderlineIcon,
  Undo2,
} from 'lucide-react';
import { cn } from '../../lib/utils';
import { Button } from './button';

const TEXT_COLORS = [
  { label: 'Siyah', value: '#18181b' },
  { label: 'Gri', value: '#71717a' },
  { label: 'Kırmızı', value: '#dc2626' },
  { label: 'Turuncu', value: '#ea580c' },
  { label: 'Yeşil', value: '#16a34a' },
  { label: 'Mavi', value: '#2563eb' },
  { label: 'Mor', value: '#7c3aed' },
];

const HIGHLIGHT_COLORS = [
  { label: 'Sarı', value: '#fef08a' },
  { label: 'Yeşil', value: '#bbf7d0' },
  { label: 'Mavi', value: '#bfdbfe' },
  { label: 'Pembe', value: '#fbcfe8' },
  { label: 'Turuncu', value: '#fed7aa' },
];

type RichTextEditorProps = {
  value: string;
  onChange: (html: string) => void;
  /** Remount/sync key when switching documents or templates */
  contentKey?: string;
  placeholder?: string;
  className?: string;
  minHeightClassName?: string;
  disabled?: boolean;
};

function ToolbarButton({
  active,
  disabled,
  onClick,
  title,
  children,
}: {
  active?: boolean;
  disabled?: boolean;
  onClick: () => void;
  title: string;
  children: ReactNode;
}) {
  return (
    <Button
      type="button"
      size="icon"
      variant={active ? 'secondary' : 'ghost'}
      className="h-8 w-8"
      disabled={disabled}
      title={title}
      onClick={onClick}
    >
      {children}
    </Button>
  );
}

export function RichTextEditor({
  value,
  onChange,
  contentKey,
  placeholder = 'Metni yazın…',
  className,
  minHeightClassName = 'min-h-[220px]',
  disabled = false,
}: RichTextEditorProps) {
  const editor = useEditor(
    {
      extensions: [
        StarterKit.configure({
          heading: { levels: [1, 2, 3] },
        }),
        Underline,
        TextStyle,
        Color,
        Highlight.configure({ multicolor: true }),
        Link.configure({
          openOnClick: false,
          HTMLAttributes: { rel: 'noopener noreferrer', target: '_blank' },
        }),
        TextAlign.configure({ types: ['heading', 'paragraph'] }),
        Placeholder.configure({ placeholder }),
      ],
      content: value || '',
      editable: !disabled,
      immediatelyRender: false,
      onUpdate: ({ editor: ed }) => {
        onChange(ed.getHTML());
      },
      editorProps: {
        attributes: {
          class: cn(
            'tiptap focus:outline-none px-3 py-2 text-sm leading-relaxed',
            minHeightClassName
          ),
        },
      },
    },
    [contentKey]
  );

  useEffect(() => {
    if (!editor) return;
    const next = value || '';
    if (next !== editor.getHTML()) {
      editor.commands.setContent(next, { emitUpdate: false });
    }
  }, [value, contentKey, editor]);

  useEffect(() => {
    if (!editor) return;
    editor.setEditable(!disabled);
  }, [disabled, editor]);

  if (!editor) return null;

  const setLink = () => {
    const prev = editor.getAttributes('link').href as string | undefined;
    const url = window.prompt('Bağlantı URL', prev || 'https://');
    if (url === null) return;
    if (!url.trim()) {
      editor.chain().focus().extendMarkRange('link').unsetLink().run();
      return;
    }
    editor.chain().focus().extendMarkRange('link').setLink({ href: url.trim() }).run();
  };

  return (
    <div className={cn('rounded-md border border-input bg-background overflow-hidden', className)}>
      <div className="flex flex-wrap items-center gap-0.5 border-b border-border bg-muted/40 px-1.5 py-1">
        <ToolbarButton
          title="Geri al"
          disabled={disabled || !editor.can().undo()}
          onClick={() => editor.chain().focus().undo().run()}
        >
          <Undo2 className="w-3.5 h-3.5" />
        </ToolbarButton>
        <ToolbarButton
          title="İleri al"
          disabled={disabled || !editor.can().redo()}
          onClick={() => editor.chain().focus().redo().run()}
        >
          <Redo2 className="w-3.5 h-3.5" />
        </ToolbarButton>

        <span className="mx-1 h-5 w-px bg-border" />

        <select
          className="h-8 rounded-md border border-transparent bg-transparent px-1.5 text-xs"
          disabled={disabled}
          value={
            editor.isActive('heading', { level: 1 })
              ? 'h1'
              : editor.isActive('heading', { level: 2 })
                ? 'h2'
                : editor.isActive('heading', { level: 3 })
                  ? 'h3'
                  : 'p'
          }
          onChange={(e) => {
            const v = e.target.value;
            const chain = editor.chain().focus();
            if (v === 'h1') chain.toggleHeading({ level: 1 }).run();
            else if (v === 'h2') chain.toggleHeading({ level: 2 }).run();
            else if (v === 'h3') chain.toggleHeading({ level: 3 }).run();
            else chain.setParagraph().run();
          }}
          title="Başlık"
        >
          <option value="p">Paragraf</option>
          <option value="h1">Başlık 1</option>
          <option value="h2">Başlık 2</option>
          <option value="h3">Başlık 3</option>
        </select>

        <span className="mx-1 h-5 w-px bg-border" />

        <ToolbarButton
          title="Kalın"
          active={editor.isActive('bold')}
          disabled={disabled}
          onClick={() => editor.chain().focus().toggleBold().run()}
        >
          <Bold className="w-3.5 h-3.5" />
        </ToolbarButton>
        <ToolbarButton
          title="İtalik"
          active={editor.isActive('italic')}
          disabled={disabled}
          onClick={() => editor.chain().focus().toggleItalic().run()}
        >
          <Italic className="w-3.5 h-3.5" />
        </ToolbarButton>
        <ToolbarButton
          title="Altı çizili"
          active={editor.isActive('underline')}
          disabled={disabled}
          onClick={() => editor.chain().focus().toggleUnderline().run()}
        >
          <UnderlineIcon className="w-3.5 h-3.5" />
        </ToolbarButton>
        <ToolbarButton
          title="Üstü çizili"
          active={editor.isActive('strike')}
          disabled={disabled}
          onClick={() => editor.chain().focus().toggleStrike().run()}
        >
          <Strikethrough className="w-3.5 h-3.5" />
        </ToolbarButton>

        <span className="mx-1 h-5 w-px bg-border" />

        <label className="inline-flex h-8 items-center gap-1 px-1.5 text-[11px] text-muted-foreground" title="Metin rengi">
          <span
            className="inline-block h-3.5 w-3.5 rounded-sm border border-border"
            style={{ backgroundColor: (editor.getAttributes('textStyle').color as string) || '#18181b' }}
          />
          <select
            className="bg-transparent text-xs max-w-[88px]"
            disabled={disabled}
            value={(editor.getAttributes('textStyle').color as string) || ''}
            onChange={(e) => {
              const v = e.target.value;
              if (!v) editor.chain().focus().unsetColor().run();
              else editor.chain().focus().setColor(v).run();
            }}
          >
            <option value="">Renk</option>
            {TEXT_COLORS.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
        </label>

        <label className="inline-flex h-8 items-center gap-1 px-1.5 text-[11px] text-muted-foreground" title="Vurgu">
          <Highlighter className="w-3.5 h-3.5" />
          <select
            className="bg-transparent text-xs max-w-[88px]"
            disabled={disabled}
            value={(editor.getAttributes('highlight').color as string) || ''}
            onChange={(e) => {
              const v = e.target.value;
              if (!v) editor.chain().focus().unsetHighlight().run();
              else editor.chain().focus().toggleHighlight({ color: v }).run();
            }}
          >
            <option value="">Vurgu</option>
            {HIGHLIGHT_COLORS.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
        </label>

        <span className="mx-1 h-5 w-px bg-border" />

        <ToolbarButton
          title="Sola hizala"
          active={editor.isActive({ textAlign: 'left' })}
          disabled={disabled}
          onClick={() => editor.chain().focus().setTextAlign('left').run()}
        >
          <AlignLeft className="w-3.5 h-3.5" />
        </ToolbarButton>
        <ToolbarButton
          title="Ortala"
          active={editor.isActive({ textAlign: 'center' })}
          disabled={disabled}
          onClick={() => editor.chain().focus().setTextAlign('center').run()}
        >
          <AlignCenter className="w-3.5 h-3.5" />
        </ToolbarButton>
        <ToolbarButton
          title="Sağa hizala"
          active={editor.isActive({ textAlign: 'right' })}
          disabled={disabled}
          onClick={() => editor.chain().focus().setTextAlign('right').run()}
        >
          <AlignRight className="w-3.5 h-3.5" />
        </ToolbarButton>

        <span className="mx-1 h-5 w-px bg-border" />

        <ToolbarButton
          title="Madde listesi"
          active={editor.isActive('bulletList')}
          disabled={disabled}
          onClick={() => editor.chain().focus().toggleBulletList().run()}
        >
          <List className="w-3.5 h-3.5" />
        </ToolbarButton>
        <ToolbarButton
          title="Numaralı liste"
          active={editor.isActive('orderedList')}
          disabled={disabled}
          onClick={() => editor.chain().focus().toggleOrderedList().run()}
        >
          <ListOrdered className="w-3.5 h-3.5" />
        </ToolbarButton>
        <ToolbarButton
          title="Bağlantı"
          active={editor.isActive('link')}
          disabled={disabled}
          onClick={setLink}
        >
          <Link2 className="w-3.5 h-3.5" />
        </ToolbarButton>
      </div>

      <EditorContent editor={editor} />
    </div>
  );
}
