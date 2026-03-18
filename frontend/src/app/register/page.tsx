'use client';

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";

// Динамический импорт компонента кроппера (чтобы избежать SSR проблем)
const AvatarCropper = dynamic(() => import('@/components/AvatarCropper'), {
  ssr: false,
});

interface RegisterFormData {
  // Шаг 1: Основная информация
  first_name: string;
  last_name: string;
  email: string;
  phone_number: string;
  password: string;
  confirmPassword: string;
  
  // Шаг 2: Личные данные
  birth_date: string;
  gender: 1 | 2 | '';
  patronymic: string;
  
  // Шаг 3: Фото профиля
  avatar: string;
  
  // Шаг 4: Дополнительно
  telegram: string;
  whatsapp: string;
  wechat: string;
}

export default function Register() {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [avatarPreview, setAvatarPreview] = useState<string | null>(null);
  
  // Состояния для кроппера
  const [showCropper, setShowCropper] = useState(false);
  const [tempImage, setTempImage] = useState<string>('');
  
  const [formData, setFormData] = useState<RegisterFormData>({
    first_name: '',
    last_name: '',
    email: '',
    phone_number: '',
    password: '',
    confirmPassword: '',
    birth_date: '',
    gender: '',
    patronymic: '',
    avatar: '',
    telegram: '',
    whatsapp: '',
    wechat: '',
  });

  const totalSteps = 4;
  const stepTitles = [
    'Личные данные',
    'Контакты и пароль',
    'Фото профиля',
    'Дополнительно'
  ];

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    setError(null);
    // Очистить ошибку конкретного поля при изменении
    if (fieldErrors[name]) {
      setFieldErrors(prev => {
        const updated = { ...prev };
        delete updated[name];
        return updated;
      });
    }
  };

  const handleAvatarChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Проверка размера (макс 10MB для исходного файла)
    if (file.size > 10 * 1024 * 1024) {
      setError('Размер файла не должен превышать 10MB');
      return;
    }

    // Проверка типа
    if (!file.type.startsWith('image/')) {
      setError('Выберите изображение');
      return;
    }

    const reader = new FileReader();
    reader.onloadend = () => {
      const base64 = reader.result as string;
      
      // Проверка размера изображения
      const img = new Image();
      img.onload = () => {
        if (img.width < 200 || img.height < 200) {
          setError('Изображение слишком маленькое. Минимум 200x200 пикселей');
          return;
        }
        
        // Показываем кроппер
        setTempImage(base64);
        setShowCropper(true);
        setError(null);
      };
      img.src = base64;
    };
    reader.readAsDataURL(file);
  };

  const handleCropComplete = (croppedImage: string) => {
    setFormData(prev => ({ ...prev, avatar: croppedImage }));
    setAvatarPreview(croppedImage);
    setShowCropper(false);
    setTempImage('');
    setError(null);
  };

  const handleCropCancel = () => {
    setShowCropper(false);
    setTempImage('');
  };

  const validateStep = (step: number): boolean => {
    setError(null);

    switch (step) {
      case 1:
        // Шаг 1: Личные данные (ФИО, дата рождения, пол)
        if (!formData.first_name.trim()) {
          setError('Введите имя');
          return false;
        }
        if (!formData.last_name.trim()) {
          setError('Введите фамилию');
          return false;
        }
        if (!formData.birth_date) {
          setError('Выберите дату рождения');
          return false;
        }
        if (!formData.gender) {
          setError('Выберите пол');
          return false;
        }
        return true;

      case 2:
        // Шаг 2: Контакты и пароль
        if (!formData.email.trim() || !formData.email.includes('@')) {
          setError('Введите корректный email');
          return false;
        }
        if (!formData.phone_number.trim()) {
          setError('Введите номер телефона');
          return false;
        }
        if (formData.password.length < 6) {
          setError('Пароль должен содержать минимум 6 символов');
          return false;
        }
        if (formData.password !== formData.confirmPassword) {
          setError('Пароли не совпадают');
          return false;
        }
        return true;

      case 3:
        // Шаг 3: Фото профиля
        if (!formData.avatar) {
          setError('Загрузите фото профиля');
          return false;
        }
        return true;

      case 4:
        // Шаг 4: Дополнительно (опциональный)
        return true;

      default:
        return true;
    }
  };

  const handleNext = () => {
    if (validateStep(currentStep)) {
      setCurrentStep(prev => Math.min(prev + 1, totalSteps));
    }
  };

  const handleBack = () => {
    setCurrentStep(prev => Math.max(prev - 1, 1));
    setError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validateStep(currentStep)) return;
    
    if (currentStep < totalSteps) {
      handleNext();
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const registerData = {
        first_name: formData.first_name,
        last_name: formData.last_name,
        email: formData.email,
        phone_number: formData.phone_number,
        password: formData.password,
        birth_date: formData.birth_date,
        gender: Number(formData.gender), // Конвертируем в число
        // Убираем data URI prefix из base64
        avatar: formData.avatar?.replace(/^data:image\/\w+;base64,/, '') || '',
        patronymic: formData.patronymic || undefined,
        telegram: formData.telegram || undefined,
        whatsapp: formData.whatsapp || undefined,
        wechat: formData.wechat || undefined,
      };

      const response = await fetch('/api/v1/auth/register/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(registerData),
      });

      const data = await response.json();

      if (!response.ok) {
        // Очищаем предыдущие ошибки
        setError(null);
        setFieldErrors({});
        
        // Обработка field-specific ошибок
        if (data.error === 'email_taken') {
          setFieldErrors({ email: 'Email уже зарегистрирован. Войдите в существующий аккаунт.' });
          setCurrentStep(1); // Вернуть на шаг с email
        } else if (data.error === 'phone_taken' || data.phone_number) {
          const phoneError = data.phone_number 
            ? (Array.isArray(data.phone_number) ? data.phone_number[0] : data.phone_number)
            : 'Номер телефона уже используется другим аккаунтом.';
          setFieldErrors({ phone_number: phoneError });
          setCurrentStep(1); // Вернуть на шаг с телефоном
        } else if (data.error === 'invalid_phone') {
          setFieldErrors({ phone_number: 'Некорректный формат номера телефона.' });
          setCurrentStep(1);
        } else if (data.email) {
          const emailError = Array.isArray(data.email) ? data.email[0] : data.email;
          setFieldErrors({ email: emailError });
          setCurrentStep(1);
        } else if (data.detail) {
          // Общая ошибка (например, IP-ограничение)
          setError(data.detail);
        } else {
          setError('Произошла ошибка при регистрации. Проверьте введённые данные.');
        }
        return;
      }

      // Успешная регистрация - редирект на страницу подтверждения email
      router.push(`/verify-email?email=${encodeURIComponent(formData.email)}`);
      
    } catch (err) {
      setError('Не удалось подключиться к серверу');
      console.error('Registration error:', err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-sky-50 to-white text-gray-900">
      <div className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center px-6 py-12 sm:px-10">
        <div className="mx-auto w-full max-w-lg rounded-2xl bg-white p-8 shadow-xl ring-1 ring-gray-100">
          {/* Заголовок */}
          <div className="mb-6">
            <h1 className="mb-2 text-3xl font-semibold tracking-tight text-gray-900">
              Регистрация
            </h1>
            <p className="text-sm text-gray-600">
              {stepTitles[currentStep - 1]} • Шаг {currentStep} из {totalSteps}
            </p>
          </div>

          {/* Прогресс-бар */}
          <div className="mb-8">
            <div className="flex gap-2">
              {Array.from({ length: totalSteps }).map((_, index) => (
                <div
                  key={index}
                  className={`h-2 flex-1 rounded-full transition-all ${
                    index < currentStep
                      ? 'bg-sky-500'
                      : index === currentStep - 1
                      ? 'bg-sky-300'
                      : 'bg-gray-200'
                  }`}
                />
              ))}
            </div>
          </div>

          {/* Ошибка */}
          {error && (
            <div className="mb-6 rounded-lg bg-red-50 border border-red-200 p-4 text-sm text-red-800">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Шаг 1: Личные данные */}
            {currentStep === 1 && (
              <div className="space-y-4">
                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <label className="mb-2 block text-sm font-medium text-gray-700" htmlFor="first_name">
                      Имя <span className="text-red-500">*</span>
                    </label>
                    <input
                      id="first_name"
                      name="first_name"
                      type="text"
                      required
                      value={formData.first_name}
                      onChange={handleInputChange}
                      className="w-full rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-900 transition focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
                      placeholder="Иван"
                    />
                  </div>
                  <div>
                    <label className="mb-2 block text-sm font-medium text-gray-700" htmlFor="last_name">
                      Фамилия <span className="text-red-500">*</span>
                    </label>
                    <input
                      id="last_name"
                      name="last_name"
                      type="text"
                      required
                      value={formData.last_name}
                      onChange={handleInputChange}
                      className="w-full rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-900 transition focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
                      placeholder="Иванов"
                    />
                  </div>
                </div>

                <div>
                  <label className="mb-2 block text-sm font-medium text-gray-700" htmlFor="patronymic">
                    Отчество
                  </label>
                  <input
                    id="patronymic"
                    name="patronymic"
                    type="text"
                    value={formData.patronymic}
                    onChange={handleInputChange}
                    className="w-full rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-900 transition focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
                    placeholder="Иванович"
                  />
                </div>

                <div>
                  <label className="mb-2 block text-sm font-medium text-gray-700" htmlFor="birth_date">
                    Дата рождения <span className="text-red-500">*</span>
                  </label>
                  <input
                    id="birth_date"
                    name="birth_date"
                    type="date"
                    required
                    value={formData.birth_date}
                    onChange={handleInputChange}
                    max={new Date().toISOString().split('T')[0]}
                    className="w-full rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-900 transition focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
                  />
                </div>

                <div>
                  <label className="mb-2 block text-sm font-medium text-gray-700" htmlFor="gender">
                    Пол <span className="text-red-500">*</span>
                  </label>
                  <select
                    id="gender"
                    name="gender"
                    required
                    value={formData.gender}
                    onChange={handleInputChange}
                    className="w-full rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-900 transition focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
                  >
                    <option value="">Выберите пол</option>
                    <option value="1">Мужской</option>
                    <option value="2">Женский</option>
                  </select>
                </div>
              </div>
            )}

            {/* Шаг 2: Контакты и пароль */}
            {currentStep === 2 && (
              <div className="space-y-4">
                <div>
                  <label className="mb-2 block text-sm font-medium text-gray-700" htmlFor="email">
                    Email <span className="text-red-500">*</span>
                  </label>
                  <input
                    id="email"
                    name="email"
                    type="email"
                    required
                    value={formData.email}
                    onChange={handleInputChange}
                    autoComplete="email"
                    className={`w-full rounded-lg border px-4 py-3 text-sm text-gray-900 transition focus:outline-none focus:ring-2 ${
                      fieldErrors.email 
                        ? 'border-red-300 bg-red-50 focus:border-red-500 focus:ring-red-100' 
                        : 'border-gray-200 bg-gray-50 focus:border-sky-500 focus:bg-white focus:ring-sky-100'
                    }`}
                    placeholder="example@mail.com"
                  />
                  {fieldErrors.email && (
                    <p className="mt-1 text-sm text-red-600">{fieldErrors.email}</p>
                  )}
                </div>

                <div>
                  <label className="mb-2 block text-sm font-medium text-gray-700" htmlFor="phone_number">
                    Телефон <span className="text-red-500">*</span>
                  </label>
                  <input
                    id="phone_number"
                    name="phone_number"
                    type="tel"
                    required
                    value={formData.phone_number}
                    onChange={handleInputChange}
                    autoComplete="tel"
                    className={`w-full rounded-lg border px-4 py-3 text-sm text-gray-900 transition focus:outline-none focus:ring-2 ${
                      fieldErrors.phone_number 
                        ? 'border-red-300 bg-red-50 focus:border-red-500 focus:ring-red-100' 
                        : 'border-gray-200 bg-gray-50 focus:border-sky-500 focus:bg-white focus:ring-sky-100'
                    }`}
                    placeholder="+7 (900) 123-45-67"
                  />
                  {fieldErrors.phone_number ? (
                    <p className="mt-1 text-sm text-red-600">{fieldErrors.phone_number}</p>
                  ) : (
                    <p className="mt-1 text-xs text-gray-500">Формат: +7XXXXXXXXXX</p>
                  )}
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <label className="mb-2 block text-sm font-medium text-gray-700" htmlFor="password">
                      Пароль <span className="text-red-500">*</span>
                    </label>
                    <input
                      id="password"
                      name="password"
                      type="password"
                      required
                      value={formData.password}
                      onChange={handleInputChange}
                      autoComplete="new-password"
                      className="w-full rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-900 transition focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
                      placeholder="••••••••"
                    />
                  </div>
                  <div>
                    <label className="mb-2 block text-sm font-medium text-gray-700" htmlFor="confirmPassword">
                      Повторите пароль <span className="text-red-500">*</span>
                    </label>
                    <input
                      id="confirmPassword"
                      name="confirmPassword"
                      type="password"
                      required
                      value={formData.confirmPassword}
                      onChange={handleInputChange}
                      autoComplete="new-password"
                      className="w-full rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-900 transition focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
                      placeholder="••••••••"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Шаг 3: Фото профиля */}
            {currentStep === 3 && (
              <div className="space-y-4">
                <div>
                  <label className="mb-2 block text-sm font-medium text-gray-700">
                    Фото профиля <span className="text-red-500">*</span>
                  </label>
                  
                  {avatarPreview ? (
                    <div className="flex flex-col items-center gap-4">
                      <img
                        src={avatarPreview}
                        alt="Предпросмотр"
                        className="h-40 w-40 rounded-full object-cover ring-4 ring-sky-100"
                      />
                      <button
                        type="button"
                        onClick={() => {
                          setFormData(prev => ({ ...prev, avatar: '' }));
                          setAvatarPreview(null);
                        }}
                        className="text-sm text-sky-600 hover:text-sky-700 font-medium"
                      >
                        Изменить фото
                      </button>
                    </div>
                  ) : (
                    <div className="flex flex-col items-center gap-4">
                      <div className="w-full">
                        <label
                          htmlFor="avatar-upload"
                          className="flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-gray-300 bg-gray-50 px-6 py-12 transition hover:border-sky-400 hover:bg-sky-50"
                        >
                          <svg
                            className="h-12 w-12 text-gray-400"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M12 6v6m0 0v6m0-6h6m-6 0H6"
                            />
                          </svg>
                          <p className="mt-2 text-sm font-medium text-gray-700">
                            Загрузить фото
                          </p>
                          <p className="mt-1 text-xs text-gray-500">
                            PNG, JPG до 5MB
                          </p>
                          <input
                            id="avatar-upload"
                            type="file"
                            accept="image/*"
                            onChange={handleAvatarChange}
                            className="hidden"
                          />
                        </label>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Шаг 4: Дополнительно */}
            {currentStep === 4 && (
              <div className="space-y-4">
                <p className="text-sm text-gray-600 mb-4">
                  Эти поля необязательны, но помогут коллегам связаться с вами
                </p>

                <div>
                  <label className="mb-2 block text-sm font-medium text-gray-700" htmlFor="telegram">
                    Telegram
                  </label>
                  <input
                    id="telegram"
                    name="telegram"
                    type="text"
                    value={formData.telegram}
                    onChange={handleInputChange}
                    className="w-full rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-900 transition focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
                    placeholder="@username"
                  />
                </div>

                <div>
                  <label className="mb-2 block text-sm font-medium text-gray-700" htmlFor="whatsapp">
                    WhatsApp
                  </label>
                  <input
                    id="whatsapp"
                    name="whatsapp"
                    type="text"
                    value={formData.whatsapp}
                    onChange={handleInputChange}
                    className="w-full rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-900 transition focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
                    placeholder="+7 (900) 123-45-67"
                  />
                </div>

                <div>
                  <label className="mb-2 block text-sm font-medium text-gray-700" htmlFor="wechat">
                    WeChat
                  </label>
                  <input
                    id="wechat"
                    name="wechat"
                    type="text"
                    value={formData.wechat}
                    onChange={handleInputChange}
                    className="w-full rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-900 transition focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-100"
                    placeholder="WeChat ID"
                  />
                </div>
              </div>
            )}

            {/* Кнопки навигации */}
            <div className="flex gap-3 pt-4">
              {currentStep > 1 && (
                <button
                  type="button"
                  onClick={handleBack}
                  disabled={isLoading}
                  className="flex-1 rounded-lg border border-gray-200 px-4 py-3 text-sm font-semibold text-gray-700 transition hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-200 disabled:opacity-50"
                >
                  Назад
                </button>
              )}
              
              <button
                type="submit"
                disabled={isLoading}
                className="flex-1 rounded-lg bg-sky-500 px-4 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-sky-600 focus:outline-none focus:ring-2 focus:ring-sky-300 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isLoading ? (
                  <span className="flex items-center justify-center gap-2">
                    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    Подождите...
                  </span>
                ) : currentStep === totalSteps ? (
                  'Создать аккаунт'
                ) : (
                  'Продолжить'
                )}
              </button>
            </div>

            {currentStep === 1 && (
              <Link
                href="/login"
                className="mt-4 flex w-full items-center justify-center rounded-lg border border-gray-200 px-4 py-3 text-sm font-semibold text-sky-700 transition hover:border-sky-200 hover:bg-sky-50 focus:outline-none focus:ring-2 focus:ring-sky-100"
              >
                Уже есть аккаунт? Войти
              </Link>
            )}
          </form>

          {currentStep === totalSteps && (
            <p className="mt-6 text-center text-xs text-gray-500">
              Регистрируясь, вы принимаете условия использования и политику конфиденциальности
            </p>
          )}
        </div>
      </div>

      {/* Модальное окно кроппера */}
      {showCropper && tempImage && (
        <AvatarCropper
          initialImage={tempImage}
          onCropComplete={handleCropComplete}
          onCancel={handleCropCancel}
        />
      )}
    </div>
  );
}
