import test from 'node:test';
import assert from 'node:assert/strict';

import { validateAuthForm } from '../auth-form.js';

test('login requires username and password', () => {
  assert.deepEqual(
    validateAuthForm('login', { username: '', password: '' }),
    {
      username: '用户名必填',
      password: '密码必填',
    },
  );
});

test('register validates email and terms', () => {
  const errors = validateAuthForm('register', {
    username: 'neo',
    email: 'bad-email',
    password: '12345678',
    confirmPassword: '12345678',
    agreeTerms: false,
  });

  assert.equal(errors.email, '电子邮箱格式不正确');
  assert.equal(errors.agreeTerms, '您必须同意服务条款和隐私政策');
});
