const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function validateAuthForm(mode, formData) {
  const errors = {};

  if (!formData.username?.trim()) {
    errors.username = '用户名必填';
  }

  if (!formData.password) {
    errors.password = '密码必填';
  }

  if (mode === 'register') {
    if (!formData.email?.trim()) {
      errors.email = '电子邮箱必填';
    } else if (!EMAIL_PATTERN.test(formData.email)) {
      errors.email = '电子邮箱格式不正确';
    }

    if (formData.password && formData.password.length < 8) {
      errors.password = '密码长度至少为8位';
    }

    if (formData.password !== formData.confirmPassword) {
      errors.confirmPassword = '两次输入的密码不一致';
    }

    if (!formData.agreeTerms) {
      errors.agreeTerms = '您必须同意服务条款和隐私政策';
    }
  }

  return errors;
}
