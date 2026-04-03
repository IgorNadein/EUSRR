/**
 * ScrollableMessageList - классовый компонент для управления скроллом
 * Реализует логику из @chatscope/chat-ui-kit-react для предотвращения "прыжков"
 * 
 * Основные техники:
 * - getSnapshotBeforeUpdate: сохранение состояния перед React обновлением
 * - componentDidUpdate: восстановление позиции после обновления
 * - ResizeObserver: отслеживание изменений высоты контейнера
 * - isSticked: проверка "прилипания" к низу списка
 */

import React, { Component, createRef, ReactNode, forwardRef } from 'react';

export interface ScrollableMessageListProps {
  children: ReactNode;
  autoScrollToBottom?: boolean;
  autoScrollToBottomOnMount?: boolean;
  scrollBehavior?: ScrollBehavior;
  className?: string;
  onScroll?: () => void;
  onYReachStart?: () => void;
  onYReachEnd?: () => void;
}

interface Snapshot {
  sticky: boolean;
  clientHeight: number;
  scrollHeight: number;
  diff: number;
  anchorMessageId: string | null;
  anchorOffsetTop: number | null;
}

export class ScrollableMessageListInner extends Component<ScrollableMessageListProps> {
  public containerRef = createRef<HTMLDivElement>();
  private scrollPointRef = createRef<HTMLDivElement>();
  private lastClientHeight = 0;
  private lastScrollHeight = 0; // Для отслеживания изменения высоты контента (загрузка медиа)
  private preventScrollTop = false;
  private resizeObserver?: ResizeObserver;
  private mutationObserver?: MutationObserver; // Для отслеживания DOM изменений
  private scrollTicking = false;
  private resizeTicking = false;
  private noScroll = false;

  static defaultProps = {
    autoScrollToBottom: true,
    autoScrollToBottomOnMount: true,
    scrollBehavior: 'smooth' as ScrollBehavior,
  };

  private getScrollAnchor(container: HTMLDivElement): { messageId: string; offsetTop: number } | null {
    const containerRect = container.getBoundingClientRect();
    const viewportTop = containerRect.top;
    const messageElements = container.querySelectorAll<HTMLElement>('[data-message-id]');

    for (const element of messageElements) {
      const messageId = element.dataset.messageId;
      if (!messageId) {
        continue;
      }

      const rect = element.getBoundingClientRect();
      if (rect.bottom > viewportTop) {
        return {
          messageId,
          offsetTop: rect.top - containerRect.top,
        };
      }
    }

    return null;
  }

  componentDidMount() {
    // Начальный скролл вниз при монтировании
    if (this.props.autoScrollToBottomOnMount) {
      this.scrollToEnd(this.props.scrollBehavior);
    }

    const container = this.containerRef.current;
    if (!container) return;

    this.lastClientHeight = container.clientHeight;

    // Подписка на события
    window.addEventListener('resize', this.handleResize);
    container.addEventListener('scroll', this.handleScroll);

    // ResizeObserver для отслеживания изменений высоты контейнера
    if (typeof window !== 'undefined' && typeof ResizeObserver === 'function') {
      this.resizeObserver = new ResizeObserver(this.handleContainerResize);
      this.resizeObserver.observe(container);
    }

    // MutationObserver для отслеживания изменений DOM (загрузка изображений/видео)
    // Это критично для предотвращения "прыжков" скролла при загрузке медиа
    if (typeof window !== 'undefined' && typeof MutationObserver === 'function') {
      this.lastScrollHeight = container.scrollHeight;
      this.mutationObserver = new MutationObserver(this.handleContentMutation);
      this.mutationObserver.observe(container, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ['style', 'class']
      });
    }
  }

  componentWillUnmount() {
    window.removeEventListener('resize', this.handleResize);
    
    const container = this.containerRef.current;
    if (container) {
      container.removeEventListener('scroll', this.handleScroll);
    }

    if (this.resizeObserver) {
      this.resizeObserver.disconnect();
    }

    if (this.mutationObserver) {
      this.mutationObserver.disconnect();
    }
  }

  /**
   * Сохраняет состояние скролла ПЕРЕД обновлением React
   * Это ключевой метод для предотвращения "прыжков"
   */
  getSnapshotBeforeUpdate(): Snapshot | null {
    const container = this.containerRef.current;
    if (!container) return null;

    const topHeight = Math.round(container.scrollTop + container.clientHeight);
    
    // Проверяем "прилипание" к низу (с учетом погрешности в 1px для Firefox)
    const sticky =
      container.scrollHeight === topHeight ||
      container.scrollHeight + 1 === topHeight ||
      container.scrollHeight - 1 === topHeight;

    const anchor = this.getScrollAnchor(container);

    return {
      sticky,
      clientHeight: container.clientHeight,
      scrollHeight: container.scrollHeight,
      diff: container.scrollHeight - container.scrollTop,
      anchorMessageId: anchor?.messageId ?? null,
      anchorOffsetTop: anchor?.offsetTop ?? null,
    };
  }

  /**
   * Восстанавливает позицию скролла ПОСЛЕ обновления React
   */
  componentDidUpdate(_prevProps: ScrollableMessageListProps, _prevState: any, snapshot: Snapshot | null) {
    if (!snapshot) return;

    const container = this.containerRef.current;
    if (!container) return;

    const { autoScrollToBottom } = this.props;

    if (snapshot.sticky) {
      // Если был внизу - скроллим вниз (если autoScrollToBottom = true)
      if (autoScrollToBottom) {
        this.scrollToEnd(this.props.scrollBehavior);
      }
      this.preventScrollTop = true;
    } else {
      // Если был НЕ внизу - восстанавливаем позицию
      
      if (snapshot.clientHeight < this.lastClientHeight) {
        // Высота viewport уменьшилась
        const sHeight = container.scrollTop + this.lastClientHeight;
        
        // Проверяем, не стал ли sticky из-за уменьшения высоты
        if (
          container.scrollHeight === sHeight ||
          container.scrollHeight + 1 === sHeight ||
          container.scrollHeight - 1 === sHeight
        ) {
          if (autoScrollToBottom) {
            this.scrollToEnd(this.props.scrollBehavior);
            this.preventScrollTop = true;
          }
        } else {
          this.preventScrollTop = false;
        }
      } else {
        this.preventScrollTop = false;

        if (snapshot.anchorMessageId && snapshot.anchorOffsetTop !== null) {
          const anchorElement = container.querySelector<HTMLElement>(`[data-message-id="${snapshot.anchorMessageId}"]`);

          if (anchorElement) {
            const containerRect = container.getBoundingClientRect();
            const currentOffsetTop = anchorElement.getBoundingClientRect().top - containerRect.top;
            const offsetDiff = currentOffsetTop - snapshot.anchorOffsetTop;

            if (Math.abs(offsetDiff) > 0.5) {
              container.scrollTop += offsetDiff;
            }
          }
        }
      }
    }

    this.lastClientHeight = snapshot.clientHeight;
    // Обновляем lastScrollHeight чтобы MutationObserver знал о новой высоте после React updates
    this.lastScrollHeight = container.scrollHeight;
  }

  /**
   * Обработка изменений высоты контента (через MutationObserver)
   * Срабатывает когда загружаются изображения/видео и меняется scrollHeight
   */
  handleContentMutation = (mutations: MutationRecord[] = []) => {
    const container = this.containerRef.current;
    if (!container) return;

    const currentScrollHeight = container.scrollHeight;
    
    // Если высота контента изменилась
    if (currentScrollHeight !== this.lastScrollHeight) {
      const heightDiff = currentScrollHeight - this.lastScrollHeight;
      const hasChildListMutation = mutations.some((mutation) => mutation.type === 'childList');

      if (hasChildListMutation) {
        this.lastScrollHeight = currentScrollHeight;
        return;
      }
      
      // ВАЖНО: Не корректируем если scrollTop близко к 0 (это prepend operation)
      // В этом случае коррекцию делает componentDidUpdate с правильной логикой
      const isPrepend = container.scrollTop < 50;
      
      // Если пользователь НЕ внизу (не sticky) И это НЕ prepend, корректируем позицию
      // Чтобы изображения не "сдвигали" скролл
      if (!this.isSticked() && !isPrepend && heightDiff > 0) {
        // Прокручиваем на разницу высоты чтобы сохранить видимую позицию
        container.scrollTop += heightDiff;
      }
      
      this.lastScrollHeight = currentScrollHeight;
    }
  };

  /**
   * Обработка ресайза окна
   */
  handleResize = () => {
    const container = this.containerRef.current;
    if (!container) return;

    // Если контейнер стал меньше - скроллим вниз
    if (container.clientHeight < this.lastClientHeight) {
      this.scrollToEnd(this.props.scrollBehavior);
    }

    this.lastClientHeight = container.clientHeight;
  };

  /**
   * Обработка изменения высоты контейнера (через ResizeObserver)
   */
  handleContainerResize = () => {
    if (this.resizeTicking) return;

    this.resizeTicking = true;
    window.requestAnimationFrame(() => {
      const container = this.containerRef.current;
      if (!container) {
        this.resizeTicking = false;
        return;
      }

      const currentHeight = container.clientHeight;
      const diff = currentHeight - this.lastClientHeight;

      if (diff >= 1) {
        // Корректируем scrollTop при изменении высоты
        if (!this.preventScrollTop) {
          container.scrollTop = Math.round(container.scrollTop) - diff;
        }
      } else if (diff !== 0) {
        container.scrollTop = container.scrollTop - diff;
      }

      this.lastClientHeight = container.clientHeight;
      this.resizeTicking = false;
    });
  };

  /**
   * Обработка события скролла
   */
  handleScroll = () => {
    if (this.scrollTicking) return;

    this.scrollTicking = true;
    window.requestAnimationFrame(() => {
      if (!this.noScroll) {
        this.preventScrollTop = this.isSticked();
      } else {
        this.noScroll = false;
      }

      // Вызываем callback
      if (this.props.onScroll) {
        this.props.onScroll();
      }

      this.scrollTicking = false;
    });
  };

  /**
   * Проверка, находится ли скролл в самом низу
   */
  isSticked = (): boolean => {
    const container = this.containerRef.current;
    if (!container) return false;

    return (
      container.scrollHeight ===
      Math.round(container.scrollTop + container.clientHeight)
    );
  };

  /**
   * Прокрутка вниз
   */
  scrollToEnd = (scrollBehavior: ScrollBehavior = this.props.scrollBehavior || 'smooth') => {
    const container = this.containerRef.current;
    if (!container) return;

    // Принудительно ставим scrollTop на максимум — самый надёжный способ
    container.scrollTop = container.scrollHeight;

    this.lastClientHeight = container.clientHeight;
    this.noScroll = true;
  };

  /**
   * Публичный метод для программной прокрутки вниз
   */
  public scrollToBottom = (behavior: ScrollBehavior = 'smooth') => {
    this.scrollToEnd(behavior);
  };

  /**
   * Публичный метод для принудительной проверки и коррекции позиции при загрузке медиа
   * Можно вызывать из onLoad обработчиков изображений/видео для дополнительной гарантии
   */
  public updateScrollPosition = () => {
    this.handleContentMutation();
  };

  render() {
    const { children, className } = this.props;

    return (
      <div
        ref={this.containerRef}
        className={className}
        style={{
          overflowY: 'auto',
          overflowX: 'hidden',
          height: '100%',
          position: 'relative',
        }}
      >
        {children}
        {/* Невидимая точка в самом низу для scrollToEnd */}
        <div ref={this.scrollPointRef} style={{ height: 0 }} />
      </div>
    );
  }
}

// ForwardRef обертка для использования с useRef в функциональных компонентах
export const ScrollableMessageList = forwardRef<ScrollableMessageListInner, ScrollableMessageListProps>(
  (props, ref) => {
    return <ScrollableMessageListInner ref={ref as any} {...props} />;
  }
);

ScrollableMessageList.displayName = 'ScrollableMessageList';

export default ScrollableMessageList;
