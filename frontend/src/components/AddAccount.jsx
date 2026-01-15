import React, { useState, useEffect } from 'react'
import {
  Box,
  Paper,
  Typography,
  TextField,
  Button,
  Stepper,
  Step,
  StepLabel,
  Alert,
  CircularProgress,
  Snackbar,
  Grid,
  Link
} from '@mui/material'

const steps = ['Введите данные аккаунта', 'Подтвердите код', 'Введите пароль 2FA (если требуется)', 'Завершение настройки']

const AddAccount = () => {
  const [activeStep, setActiveStep] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'info' })
  const [csrfToken, setCsrfToken] = useState('')
  const [csrfError, setCsrfError] = useState('')
  const [requires2FA, setRequires2FA] = useState(false)
  
  const [formData, setFormData] = useState({
    phone_number: '',
    employee_id: '',
    employee_fio: '',
    account_note: '',
    recovery_email: '',
    verification_code: '',
    two_factor_password: ''
  })

  // Получение CSRF токена при монтировании компонента
  useEffect(() => {
    const fetchCsrfToken = async () => {
      try {
        const response = await fetch('/api/auth/csrf/', {
          credentials: 'include',
          headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
          }
        })
        if (response.ok) {
          const data = await response.json()
          setCsrfToken(data.csrf_token)
        } else {
          setCsrfError('Не удалось получить CSRF токен')
        }
      } catch (err) {
        setCsrfError('Ошибка при получении CSRF токена')
      }
    }
    fetchCsrfToken()
  }, [])

  const handleInputChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    })
  }

  const validateForm = () => {
    if (!formData.phone_number.match(/^\+?[1-9]\d{1,14}$/)) {
      return 'Введите корректный номер телефона в международном формате (например: +79991234567)'
    }
    if (!formData.employee_id.trim()) {
      return 'Введите ID сотрудника'
    }
    if (!formData.employee_fio.trim()) {
      return 'Введите ФИО сотрудника'
    }
    if (!formData.recovery_email.trim()) {
      return 'Введите email для восстановления'
    }
    if (!formData.recovery_email.includes('@')) {
      return 'Введите корректный email'
    }
    return ''
  }

  const handleSendCode = async () => {
    const validationError = validateForm()
    if (validationError) {
      setError(validationError)
      setSnackbar({
        open: true,
        message: validationError,
        severity: 'error'
      })
      return
    }

    if (!csrfToken) {
      setError('CSRF токен не получен. Пожалуйста, обновите страницу.')
      return
    }

    setLoading(true)
    setError('')
    setSuccess('')
    setRequires2FA(false)

    try {
      const response = await fetch('/api/accounts/send-code/', {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({
          phone_number: formData.phone_number,
          employee_id: formData.employee_id,
          employee_fio: formData.employee_fio,
          account_note: formData.account_note,
          recovery_email: formData.recovery_email
        })
      })
      
      const data = await response.json()
      setLoading(false)
      
      if (!response.ok) {
        setError(data.error || 'Не удалось отправить код подтверждения')
        setSnackbar({
          open: true,
          message: data.error || 'Не удалось отправить код подтверждения',
          severity: 'error'
        })
      } else {
        setSuccess(data.message || 'Код отправлен успешно')
        setSnackbar({
          open: true,
          message: data.message || 'Код отправлен успешно',
          severity: 'success'
        })
        setActiveStep(1)
      }
    } catch (err) {
      setLoading(false)
      setError('Не удалось отправить код подтверждения')
      setSnackbar({
        open: true,
        message: 'Не удалось отправить код подтверждения. Проверьте подключение.',
        severity: 'error'
      })
    }
  }

  const handleVerifyCode = async () => {
    if (!formData.verification_code.trim()) {
      setError('Введите код подтверждения')
      return
    }

    if (!csrfToken) {
      setError('CSRF токен не получен. Пожалуйста, обновите страницу.')
      return
    }

    setLoading(true)
    setError('')
    setSuccess('')

    try {
      const response = await fetch('/api/accounts/verify-code/', {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({
          phone_number: formData.phone_number,
          employee_id: formData.employee_id,
          employee_fio: formData.employee_fio,
          account_note: formData.account_note,
          recovery_email: formData.recovery_email,
          verification_code: formData.verification_code,
          two_factor_password: formData.two_factor_password || null
        })
      })
      
      const data = await response.json()
      setLoading(false)
      
      if (data.requires_2fa) {
        // Требуется пароль 2FA
        setRequires2FA(true)
        setActiveStep(2)
        setError('')
        setSuccess('Введите пароль 2FA для завершения настройки аккаунта')
        setSnackbar({
          open: true,
          message: 'Требуется пароль 2FA. Пожалуйста, введите его на следующем шаге.',
          severity: 'info'
        })
      } else if (data.error) {
        setError(data.error)
        setSnackbar({
          open: true,
          message: data.error,
          severity: 'error'
        })
      } else {
        setSuccess(data.message || 'Аккаунт успешно добавлен!')
        setSnackbar({
          open: true,
          message: data.message || 'Аккаунт успешно добавлен!',
          severity: 'success'
        })
        setActiveStep(3)
      }
    } catch (err) {
      setLoading(false)
      setError('Не удалось подтвердить код')
      setSnackbar({
        open: true,
        message: 'Не удалось подтвердить код. Проверьте подключение.',
        severity: 'error'
      })
    }
  }

  const renderStepContent = (step) => {
    switch (step) {
      case 0:
        return (
          <Box>
            {csrfError && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {csrfError}
              </Alert>
            )}
            
            <Alert severity="info" sx={{ mb: 3 }}>
              <Typography variant="body2">
                <strong>Важно:</strong> Перед добавлением аккаунта убедитесь, что:
              </Typography>
              <ul style={{ marginTop: '8px', marginBottom: '0' }}>
                <li>Номер телефона зарегистрирован в Telegram</li>
                <li>API ID и API Hash настроены в <Link href="/admin/" target="_blank">глобальных настройках</Link></li>
                <li>Код будет отправлен через SMS (если не приходит в приложение Telegram)</li>
                <li>Если аккаунт защищен 2FA, вам потребуется ввести пароль на следующем шаге</li>
              </ul>
            </Alert>
            
            <Grid container spacing={2}>
              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="Номер телефона"
                  name="phone_number"
                  value={formData.phone_number}
                  onChange={handleInputChange}
                  margin="normal"
                  placeholder="+79991234567"
                  required
                  helperText="Введите номер в международном формате"
                />
              </Grid>
              <Grid item xs={6}>
                <TextField
                  fullWidth
                  label="ID сотрудника"
                  name="employee_id"
                  value={formData.employee_id}
                  onChange={handleInputChange}
                  margin="normal"
                  required
                />
              </Grid>
              <Grid item xs={6}>
                <TextField
                  fullWidth
                  label="ФИО сотрудника"
                  name="employee_fio"
                  value={formData.employee_fio}
                  onChange={handleInputChange}
                  margin="normal"
                  required
                />
              </Grid>
              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="Email для восстановления"
                  name="recovery_email"
                  value={formData.recovery_email}
                  onChange={handleInputChange}
                  margin="normal"
                  placeholder="user@ваша-компания.com"
                  required
                  helperText="Рекомендуется использовать корпоративный email"
                />
              </Grid>
              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="Примечание к аккаунту"
                  name="account_note"
                  value={formData.account_note}
                  onChange={handleInputChange}
                  margin="normal"
                  multiline
                  rows={3}
                  helperText="Описание назначения аккаунта"
                />
              </Grid>
            </Grid>
            <Box mt={3}>
              <Button
                variant="contained"
                color="primary"
                onClick={handleSendCode}
                disabled={loading}
                size="large"
              >
                {loading ? <CircularProgress size={24} /> : 'Отправить код подтверждения'}
              </Button>
            </Box>
          </Box>
        )
      case 1:
        return (
          <Box>
            <Alert severity="info" sx={{ mb: 2 }}>
              {success || `Код подтверждения отправлен на номер ${formData.phone_number}. Проверьте SMS сообщение.`}
            </Alert>
            
            <Alert severity="warning" sx={{ mb: 2 }}>
              <Typography variant="body2">
                Если код не приходит в течение 2 минут:
              </Typography>
              <ul style={{ marginTop: '8px', marginBottom: '0' }}>
                <li>Убедитесь, что номер телефона правильный</li>
                <li>Проверьте настройки API в <Link href="/admin/" target="_blank">админ-панели</Link></li>
                <li>Попробуйте отправить код снова через 5 минут</li>
              </ul>
            </Alert>
            
            <TextField
              fullWidth
              label="Код подтверждения"
              name="verification_code"
              value={formData.verification_code}
              onChange={handleInputChange}
              margin="normal"
              required
              helperText="Введите 5-значный код из SMS"
              autoFocus
            />
            <Box mt={3} display="flex" gap={2}>
              <Button
                variant="contained"
                color="primary"
                onClick={handleVerifyCode}
                disabled={loading || !formData.verification_code}
              >
                {loading ? <CircularProgress size={24} /> : 'Подтвердить и продолжить'}
              </Button>
              <Button
                variant="outlined"
                onClick={() => {
                  setActiveStep(0)
                  setError('')
                  setSuccess('')
                  setRequires2FA(false)
                }}
              >
                Назад
              </Button>
            </Box>
          </Box>
        )
      case 2:
        return (
          <Box>
            <Alert severity="info" sx={{ mb: 2 }}>
              Для аккаунта {formData.phone_number} включена двухфакторная аутентификация (2FA).
              Пожалуйста, введите пароль 2FA для завершения настройки аккаунта.
            </Alert>
            
            <Alert severity="warning" sx={{ mb: 2 }}>
              <Typography variant="body2">
                Если вы не знаете пароль 2FA:
              </Typography>
              <ul style={{ marginTop: '8px', marginBottom: '0' }}>
                <li>Обратитесь к владельцу аккаунта за паролем</li>
                <li>Или используйте функцию восстановления через email в приложении Telegram</li>
                <li>Без пароля 2FA невозможно добавить аккаунт в систему</li>
              </ul>
            </Alert>
            
            <TextField
              fullWidth
              label="Пароль 2FA"
              name="two_factor_password"
              type="password"
              value={formData.two_factor_password}
              onChange={handleInputChange}
              margin="normal"
              required
              helperText="Введите пароль двухфакторной аутентификации"
              autoFocus
            />
            <Box mt={3} display="flex" gap={2}>
              <Button
                variant="contained"
                color="primary"
                onClick={handleVerifyCode}
                disabled={loading || !formData.two_factor_password}
              >
                {loading ? <CircularProgress size={24} /> : 'Подтвердить пароль и сохранить аккаунт'}
              </Button>
              <Button
                variant="outlined"
                onClick={() => {
                  setActiveStep(1)
                  setError('')
                  setSuccess('')
                }}
              >
                Назад
              </Button>
            </Box>
          </Box>
        )
      case 3:
        return (
          <Box>
            <Alert severity="success">
              Аккаунт успешно добавлен в систему!
            </Alert>
            <Box mt={3}>
              <Button
                variant="contained"
                color="primary"
                href="/dashboard"
              >
                Вернуться к панели управления
              </Button>
              <Button
                variant="outlined"
                color="primary"
                sx={{ ml: 2 }}
                onClick={() => {
                  setActiveStep(0)
                  setFormData({
                    phone_number: '',
                    employee_id: '',
                    employee_fio: '',
                    account_note: '',
                    recovery_email: '',
                    verification_code: '',
                    two_factor_password: ''
                  })
                  setError('')
                  setSuccess('')
                  setRequires2FA(false)
                }}
              >
                Добавить еще аккаунт
              </Button>
            </Box>
          </Box>
        )
      default:
        return null
    }
  }

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Добавление нового Telegram аккаунта
      </Typography>

      <Stepper activeStep={activeStep} sx={{ mb: 4 }}>
        {steps.map((label) => (
          <Step key={label}>
            <StepLabel>{label}</StepLabel>
          </Step>
        ))}
      </Stepper>

      <Paper sx={{ p: 3 }}>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {success && activeStep !== 3 && (
          <Alert severity="success" sx={{ mb: 2 }}>
            {success}
          </Alert>
        )}

        {renderStepContent(activeStep)}
      </Paper>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert onClose={() => setSnackbar({ ...snackbar, open: false })} severity={snackbar.severity} sx={{ width: '100%' }}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  )
}

export default AddAccount