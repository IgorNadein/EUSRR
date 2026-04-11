import { redirect } from "next/navigation";

export default function NotificationSettingsPage() {
  const [preferences, setPreferences] = useState<Preferences>({
    web_enabled: true,
    email_enabled: false,
    email_frequency: 'instant',
    push_enabled: false,
    dnd_enabled: false,
    dnd_start_time: null,
    dnd_end_time: null,
    disabled_verbs: [],
  });

  const [verbTypes, setVerbTypes] = useState<VerbType[]>([]);
  const [loading, setLoading] = useState(true);
  const [preferencesLoaded, setPreferencesLoaded] = useState(false);
  const [pushSynced, setPushSynced] = useState(false);
  const saveTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  
  const { isSupported, isSubscribed, subscribe, unsubscribe, permission, isLoading: pushLoading } = useWebPush();

  useEffect(() => {
    loadPreferences();
    loadVerbTypes();
  }, []);

  // Синхронизация с реальной браузерной подпиской при первой загрузке
  useEffect(() => {
    console.log('[Settings] Sync check:', {
      isSupported,
      preferencesLoaded,
      loading,
      pushLoading,
      pushSynced,
      'preferences.push_enabled': preferences.push_enabled,
      isSubscribed,
    });

    // Если браузер не поддерживает Push, то синхронизация не нужна
    if (!isSupported) {
      setPushSynced(true);
      return;
    }

    // Ждем пока загрузятся и preferences и push состояние
    // Синхронизируем только один раз
    if (preferencesLoaded && !loading && !pushLoading && !pushSynced) {
      if (preferences.push_enabled !== isSubscribed) {
        console.log(`[Settings] ⚠️ Syncing push state: DB=${preferences.push_enabled}, Browser=${isSubscribed}`);
        // Приоритет у браузерной подписки (это источник правды)
        setPreferences(prev => ({ ...prev, push_enabled: isSubscribed }));
      } else {
        console.log('[Settings] ✅ Push state already in sync');
      }
      setPushSynced(true);
    }
  }, [preferencesLoaded, loading, pushLoading, isSupported, pushSynced, isSubscribed, preferences.push_enabled]);

  // Автосохранение при изменении настроек (debounce 1 секунда)
  useEffect(() => {
    // Пропускаем автосохранение до первой загрузки
    if (!preferencesLoaded) {
      return;
    }

    // Очищаем предыдущий таймер
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }

    // Устанавливаем новый таймер для автосохранения
    saveTimeoutRef.current = setTimeout(async () => {
      console.log('[Settings] Auto-saving preferences...');
      try {
        const payload = {
          ...preferences,
          dnd_start_time: preferences.dnd_start_time || undefined,
          dnd_end_time: preferences.dnd_end_time || undefined,
        };
        await apiClient.updateNotificationPreferences(payload);
        console.log('[Settings] ✅ Auto-saved successfully');
      } catch (error) {
        console.error('[Settings] ❌ Auto-save failed:', error);
      }
    }, 1000); // 1 секунда после последнего изменения

    // Cleanup
    return () => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }
    };
  }, [preferences, preferencesLoaded]);

  const loadPreferences = async () => {
    try {
      setLoading(true);
      const data = await apiClient.getNotificationPreferences();
      console.log('[Settings] Preferences loaded from API:', data);
      setPreferences(data);
      setPreferencesLoaded(true);
    } catch (error) {
      console.error('Failed to load preferences:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadVerbTypes = async () => {
    try {
      const data = await apiClient.getVerbTypes();
      setVerbTypes(data.verb_types || []);
    } catch (error) {
      console.error('Failed to load verb types:', error);
    }
  };

  const toggleVerbDisabled = (verb: string) => {
    setPreferences((prev) => ({
      ...prev,
      disabled_verbs: prev.disabled_verbs.includes(verb)
        ? prev.disabled_verbs.filter((v) => v !== verb)
        : [...prev.disabled_verbs, verb],
    }));
  };

  const handlePushToggle = async (enabled: boolean) => {
    // Обновляем состояние
    setPreferences({ ...preferences, push_enabled: enabled });
    
    // Синхронизируем браузерную подписку
    if (enabled && !isSubscribed) {
      await subscribe();
    } else if (!enabled && isSubscribed) {
      await unsubscribe();
    }
  };

  const handleDndToggle = (enabled: boolean) => {
    if (enabled) {
      // При включении DND устанавливаем дефолтное время (весь день)
      setPreferences({
        ...preferences,
        dnd_enabled: true,
        dnd_start_time: preferences.dnd_start_time || '00:00',
        dnd_end_time: preferences.dnd_end_time || '23:59',
      });
    } else {
      // При выключении просто отключаем, время оставляем
      setPreferences({ ...preferences, dnd_enabled: false });
    }
  };

  const toggleTrackClass = "peer h-6 w-11 rounded-full bg-[var(--surface-tertiary)] after:absolute after:left-[2px] after:top-[2px] after:h-5 after:w-5 after:rounded-full after:border after:border-[var(--border-subtle)] after:bg-[var(--surface-primary)] after:transition-all after:content-[''] peer-checked:bg-[var(--accent-primary)] peer-checked:after:translate-x-full peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-[color:var(--accent-soft)] peer-disabled:cursor-not-allowed peer-disabled:opacity-50";

  if (loading) {
    return (
      <AppShell>
        <div className="mx-auto max-w-3xl px-4 py-6">
          <div className="app-surface-muted rounded-xl p-12 text-center">
            <div className="mx-auto mb-3 h-8 w-8 animate-spin rounded-full border-4 border-[var(--border-subtle)] border-t-[var(--accent-primary)]"></div>
            <p className="app-text-muted text-sm">Загрузка настроек...</p>
          </div>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-3xl px-4 py-6">
        {/* Заголовок */}
        <div className="mb-6">
          <Link
            href="/notifications"
            className="app-link-accent mb-3 inline-flex items-center gap-2 text-sm transition"
          >
            <ArrowLeft size={16} />
            Вернуться к уведомлениям
          </Link>
          <h1 className="text-2xl font-bold text-[var(--foreground)]">Настройки уведомлений</h1>
          <p className="app-text-muted mt-1 text-sm">
            Управляйте способами получения уведомлений · Изменения сохраняются автоматически
          </p>
        </div>

        <div className="space-y-6">
          {/* Каналы доставки */}
          <section className="app-surface rounded-xl p-6">
            <h2 className="mb-4 text-lg font-semibold text-[var(--foreground)]">Каналы доставки</h2>
            
            <div className="space-y-4">
              {/* Web уведомления */}
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-3">
                  <Bell className="app-accent-text mt-0.5 h-5 w-5" />
                  <div>
                    <h3 className="font-medium text-[var(--foreground)]">Web уведомления</h3>
                    <p className="app-text-muted text-sm">
                      Уведомления в браузере в реальном времени
                    </p>
                  </div>
                </div>
                <label className="relative inline-flex cursor-pointer items-center">
                  <input
                    type="checkbox"
                    checked={preferences.web_enabled}
                    onChange={(e) =>
                      setPreferences({ ...preferences, web_enabled: e.target.checked })
                    }
                    className="peer sr-only"
                  />
                  <div className={toggleTrackClass}></div>
                </label>
              </div>

              {/* Email уведомления */}
              <div className="space-y-3 border-t border-[var(--border-subtle)] pt-4">
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-3">
                    <Mail className="app-accent-text mt-0.5 h-5 w-5" />
                    <div>
                      <h3 className="font-medium text-[var(--foreground)]">Email уведомления</h3>
                      <p className="app-text-muted text-sm">
                        Получать уведомления на электронную почту
                      </p>
                    </div>
                  </div>
                  <label className="relative inline-flex cursor-pointer items-center">
                    <input
                      type="checkbox"
                      checked={preferences.email_enabled}
                      onChange={(e) =>
                        setPreferences({ ...preferences, email_enabled: e.target.checked })
                      }
                      className="peer sr-only"
                    />
                    <div className={toggleTrackClass}></div>
                  </label>
                </div>

                {preferences.email_enabled && (
                  <div className="ml-8">
                    <label className="mb-2 block text-sm font-medium text-[var(--foreground)]">
                      Частота отправки
                    </label>
                    <select
                      value={preferences.email_frequency}
                      onChange={(e) =>
                        setPreferences({
                          ...preferences,
                          email_frequency: e.target.value as any,
                        })
                      }
                      className="app-select w-full"
                    >
                      <option value="instant">Мгновенно</option>
                      <option value="daily">Ежедневно (дайджест)</option>
                      <option value="weekly">Еженедельно (дайджест)</option>
                      <option value="disabled">Отключено</option>
                    </select>
                  </div>
                )}
              </div>

              {/* Push уведомления */}
              <div className="space-y-3 border-t border-[var(--border-subtle)] pt-4">
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-3">
                    <Smartphone className="app-accent-text mt-0.5 h-5 w-5" />
                    <div>
                      <h3 className="font-medium text-[var(--foreground)]">Push уведомления</h3>
                      <p className="app-text-muted text-sm">
                        Системные уведомления на устройстве
                      </p>
                    </div>
                  </div>
                  <label className="relative inline-flex cursor-pointer items-center">
                    <input
                      type="checkbox"
                      checked={preferences.push_enabled}
                      onChange={(e) => handlePushToggle(e.target.checked)}
                      disabled={!isSupported || permission === 'denied'}
                      className="peer sr-only"
                    />
                    <div className={toggleTrackClass}></div>
                  </label>
                </div>

                {!isSupported && (
                  <div className="app-feedback-warning ml-8 flex items-start gap-2 rounded-lg p-3">
                    <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
                    <p className="text-xs">
                      Ваш браузер не поддерживает Push уведомления
                    </p>
                  </div>
                )}

                {isSupported && permission === 'denied' && (
                  <div className="app-feedback-danger ml-8 flex items-start gap-2 rounded-lg p-3">
                    <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
                    <p className="text-xs">
                      Вы запретили уведомления. Измените настройки браузера.
                    </p>
                  </div>
                )}

                {isSupported && permission === 'granted' && preferences.push_enabled && (
                  <div className="app-feedback-success ml-8 flex items-start gap-2 rounded-lg p-3">
                    <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
                    <p className="text-xs">
                      Push уведомления активны {isSubscribed && '(подписка активна)'}
                    </p>
                  </div>
                )}
              </div>
            </div>
          </section>

          {/* Режим "Не беспокоить" */}
          <section className="app-surface rounded-xl p-6">
            <div className="mb-4 flex items-center gap-2">
              <Moon className="app-accent-text h-5 w-5" />
              <h2 className="text-lg font-semibold text-[var(--foreground)]">Не беспокоить</h2>
            </div>

            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-medium text-[var(--foreground)]">Включить режим DND</h3>
                  <p className="app-text-muted text-sm">
                    В указанный период Email и Push будут отключены, Web уведомления — без звука
                  </p>
                </div>
                <label className="relative inline-flex cursor-pointer items-center">
                  <input
                    type="checkbox"
                    checked={preferences.dnd_enabled}
                    onChange={(e) => handleDndToggle(e.target.checked)}
                    className="peer sr-only"
                  />
                  <div className={toggleTrackClass}></div>
                </label>
              </div>

              {preferences.dnd_enabled && (
                <>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="mb-2 block text-sm font-medium text-[var(--foreground)]">
                        Начало периода
                      </label>
                      <input
                        type="time"
                        value={preferences.dnd_start_time || '00:00'}
                        onChange={(e) =>
                          setPreferences({ ...preferences, dnd_start_time: e.target.value })
                        }
                        required
                        className="app-input w-full"
                      />
                    </div>

                    <div>
                      <label className="mb-2 block text-sm font-medium text-[var(--foreground)]">
                        Конец периода
                      </label>
                      <input
                        type="time"
                        value={preferences.dnd_end_time || '23:59'}
                        onChange={(e) =>
                          setPreferences({ ...preferences, dnd_end_time: e.target.value })
                        }
                        required
                        className="app-input w-full"
                      />
                    </div>
                  </div>

                  <div className="app-selected flex items-start gap-2 rounded-lg p-3">
                    <AlertCircle className="app-accent-text mt-0.5 h-4 w-4 flex-shrink-0" />
                    <div className="app-accent-text text-xs">
                      <p className="font-medium mb-1">Режим активен</p>
                      <p>
                        С {preferences.dnd_start_time || '00:00'} до {preferences.dnd_end_time || '23:59'} будут приходить только Web уведомления (без звука). 
                        Email и Push отключены.
                        {(preferences.dnd_start_time || '00:00') > (preferences.dnd_end_time || '23:59') && (
                          <span className="block mt-1 italic">
                            Период через полночь: с {preferences.dnd_start_time} до {preferences.dnd_end_time} следующего дня.
                          </span>
                        )}
                      </p>
                    </div>
                  </div>
                </>
              )}            
            </div>
          </section>

          {/* Типы уведомлений */}
          {verbTypes.length > 0 && (
            <section className="app-surface rounded-xl p-6">
              <h2 className="mb-4 text-lg font-semibold text-[var(--foreground)]">Типы уведомлений</h2>
              <p className="app-text-muted mb-4 text-sm">
                Выберите, какие типы уведомлений вы хотите получать
              </p>

              <div className="space-y-2">
                {verbTypes.map((verbType) => (
                  <label
                    key={verbType.verb}
                    className="app-surface-muted flex cursor-pointer items-center justify-between rounded-lg p-3 transition hover:bg-[var(--surface-elevated)]"
                  >
                    <div className="flex items-center gap-3">
                      <input
                        type="checkbox"
                        checked={!preferences.disabled_verbs.includes(verbType.verb)}
                        onChange={() => toggleVerbDisabled(verbType.verb)}
                        className="h-4 w-4 rounded accent-[var(--accent-primary)]"
                      />
                      <div>
                        <div className="font-medium text-[var(--foreground)]">{getVerbName(verbType.verb)}</div>
                        <div className="app-text-muted text-xs">
                          {verbType.total} всего • {verbType.unread} непрочитанных
                        </div>
                      </div>
                    </div>
                  </label>
                ))}
              </div>
            </section>
          )}

          {/* Навигация */}
          <div className="flex justify-start">
            <Link
              href="/notifications"
              className="app-action-secondary inline-flex items-center gap-2 px-6 py-2.5"
            >
              <ArrowLeft size={16} />
              Вернуться к уведомлениям
            </Link>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
