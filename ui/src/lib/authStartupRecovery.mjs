const SAFE_CODE = /^[a-z][a-z0-9_]{0,79}$/

export function authStartupFailure(error) {
  const status = Number.isInteger(error?.status) ? error.status : null
  const rawCode = typeof error?.code === 'string' ? error.code : ''
  const code = SAFE_CODE.test(rawCode) ? rawCode : ''

  if (code === 'api_unauthorized') {
    return {
      code,
      message: 'تنظیمات ورود سرور با نسخهٔ وب سازگار نیست. مدیر سامانه باید تنظیمات احراز هویت API را بررسی کند.',
      retryable: false,
    }
  }
  if (status === 404) {
    return {
      code,
      message: 'نسخهٔ رابط و سرویس هماهنگ نیستند. مدیر سامانه باید انتشار نرم‌افزار را بررسی کند.',
      retryable: false,
    }
  }
  if (status === 401 || status === 403) {
    return {
      code,
      message: 'سرویس درخواست بررسی ورود را رد کرد. مدیر سامانه باید تنظیمات دسترسی را بررسی کند.',
      retryable: false,
    }
  }
  if (status === null || status >= 500) {
    return {
      code,
      message: 'ارتباط با سرویس ورود برقرار نشد یا سرویس هنوز آماده نیست. اتصال را بررسی کنید و دوباره تلاش کنید.',
      retryable: true,
    }
  }
  return {
    code,
    message: 'بررسی وضعیت ورود انجام نشد. اگر مشکل ادامه دارد، کد خطا را به مدیر سامانه بدهید.',
    retryable: false,
  }
}

export function authStartupRetryDelay(error, failedAttempt) {
  return failedAttempt === 0 && authStartupFailure(error).retryable ? 1200 : null
}

export function shouldRefreshAppAuthAfterError(path, code) {
  return path !== '/api/v2/app-auth/status'
    && (code === 'app_auth_required' || code === 'app_auth_session_invalid')
}
