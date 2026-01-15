import React, { useState, useEffect } from 'react'
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Button,
  Chip,
  TextField,
  Box,
  Typography,
  CircularProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Alert,
  Snackbar,
  IconButton,
  InputAdornment,
  Grid,
  Card,
  CardContent,
  Tooltip,
  Stepper,
  Step,
  StepLabel
} from '@mui/material'
import { Search, Refresh, AccountCircle, PhoneAndroid, Email, Description, Settings, LockReset } from '@mui/icons-material'
import { fetchWithAuth } from '../utils'

const Dashboard = () => {
  const [accounts, setAccounts] = useState([])
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')
  const [reclaimDialog, setReclaimDialog] = useState({ 
    open: false, 
    accountId: null, 
    accountPhone: '', 
    is2FAEnabled: false, 
    twoFactorPassword: '',
    step: 0,
    loading: false,
    error: '',
    success: ''
  })
  const [passwordDialog, setPasswordDialog] = useState({ open: false, accountId: null, accountPhone: '', oldPassword: '', newPassword: '' })
  const [detailsDialog, setDetailsDialog] = useState({ open: false, accountId: null, accountPhone: '', details: '' })
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'info' })
  const [refreshing, setRefreshing] = useState(false)
  const [stats, setStats] = useState({ total: 0, active: 0, pending: 0, reclaimed: 0 })
  const [apiSettingsDialog, setApiSettingsDialog] = useState({ open: false, apiId: '', apiHash: '', checking: false, checkResult: null })
  const [reauthorizeDialog, setReauthorizeDialog] = useState({ 
    open: false, 
    accountId: null, 
    accountPhone: '',
    step: 0,
    loading: false,
    error: '',
    success: '',
    requires2FA: false,
    verificationCode: '',
    twoFactorPassword: ''
  })

  const reclaimSteps = ['Подтверждение', 'Ввод пароля 2FA', 'Завершение']
  const reauthorizeSteps = ['Отправка кода', 'Ввод кода подтверждения', 'Ввод пароля 2FA (если требуется)']

  const fetchAccounts = async () => {
    setLoading(true)
    try {
      const response = await fetchWithAuth('/api/accounts/')
      if (response.ok) {
        const data = await response.json()
        setAccounts(data)
        
        // Calculate statistics
        const total = data.length
        const active = data.filter(a => a.account_status === 'active').length
        const pending = data.filter(a => a.account_status === 'pending' || a.account_status === 'pending_2fa' || a.account_status === 'pending_reauthorization').length
        const reclaimed = data.filter(a => a.account_status === 'reclaimed').length
        
        setStats({ total, active, pending, reclaimed })
      } else {
        setSnackbar({
          open: true,
          message: 'Не удалось загрузить аккаунты',
          severity: 'error'
        })
      }
    } catch (err) {
      console.error('Ошибка загрузки аккаунтов:', err)
      setSnackbar({
        open: true,
        message: 'Не удалось загрузить аккаунты. Проверьте подключение к бэкенду.',
        severity: 'error'
      })
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    fetchAccounts()
  }, [])

  const handleRefresh = () => {
    setRefreshing(true)
    fetchAccounts()
  }

  const handleChangePassword = (accountId, accountPhone) => {
    setPasswordDialog({ open: true, accountId, accountPhone, oldPassword: '', newPassword: '' })
  }

  const confirmChangePassword = async () => {
    const { accountId, oldPassword, newPassword } = passwordDialog
    
    try {
      const response = await fetchWithAuth(`/api/accounts/${accountId}/change-password/`, {
        method: 'POST',
        body: JSON.stringify({
          old_password: oldPassword,
          new_password: newPassword || 'CorporateSecurePassword123!'
        })
      })
      
      const data = await response.json()
      if (data.message) {
        setSnackbar({
          open: true,
          message: data.message,
          severity: 'success'
        })
      } else if (data.error) {
        setSnackbar({
          open: true,
          message: data.error,
          severity: 'error'
        })
      }
      fetchAccounts()
    } catch (err) {
      setSnackbar({
        open: true,
        message: 'Не удалось изменить пароль. Проверьте подключение к бэкенду.',
        severity: 'error'
      })
    }
    
    setPasswordDialog({ open: false, accountId: null, accountPhone: '', oldPassword: '', newPassword: '' })
  }

  const handleAction = async (action, accountId, accountPhone) => {
    if (action === 'details') {
      try {
        const response = await fetchWithAuth(`/api/accounts/${accountId}/details/`)
        const data = await response.json()
        if (data.details) {
          setDetailsDialog({
            open: true,
            accountId,
            accountPhone,
            details: data.details
          })
        } else if (data.error) {
          setSnackbar({
            open: true,
            message: data.error,
            severity: 'error'
          })
        }
      } catch (err) {
        setSnackbar({
          open: true,
          message: 'Не удалось получить детали аккаунта. Проверьте подключение к бэкенду.',
          severity: 'error'
        })
      }
      return
    }
    
    let url = ''
    if (action === 'delete-session') {
      url = `/api/accounts/${accountId}/delete-session/`
    }
    
    try {
      const response = await fetchWithAuth(url, {
        method: 'POST'
      })
      
      const data = await response.json()
      if (data.message) {
        setSnackbar({
          open: true,
          message: data.message,
          severity: 'success'
        })
      } else if (data.error) {
        setSnackbar({
          open: true,
          message: data.error,
          severity: 'error'
        })
      }
      fetchAccounts()
    } catch (err) {
      setSnackbar({
        open: true,
        message: 'Не удалось выполнить действие. Проверьте подключение к бэкенду.',
        severity: 'error'
      })
    }
  }

  const handleReclaim = (accountId, accountPhone, is2FAEnabled) => {
    setReclaimDialog({ 
      open: true, 
      accountId, 
      accountPhone, 
      is2FAEnabled,
      twoFactorPassword: '',
      step: is2FAEnabled ? 1 : 0,
      loading: false,
      error: '',
      success: ''
    })
  }

  const handleReclaimStep = async () => {
    const { accountId, twoFactorPassword, step } = reclaimDialog
    
    if (step === 0) {
      // Переходим к следующему шагу или отправляем запрос
      if (reclaimDialog.is2FAEnabled) {
        setReclaimDialog({...reclaimDialog, step: 1})
      } else {
        // Отправляем запрос без пароля
        setReclaimDialog({...reclaimDialog, loading: true})
        try {
          const response = await fetchWithAuth(`/api/accounts/${accountId}/reclaim/`, {
            method: 'POST',
            body: JSON.stringify({})
          })
          
          const data = await response.json()
          if (data.message) {
            setReclaimDialog({...reclaimDialog, loading: false, step: 2, success: data.message})
            fetchAccounts()
          } else if (data.error) {
            if (data.requires_2fa) {
              setReclaimDialog({...reclaimDialog, loading: false, step: 1, error: data.error})
            } else {
              setReclaimDialog({...reclaimDialog, loading: false, error: data.error})
            }
          }
        } catch (err) {
          setReclaimDialog({...reclaimDialog, loading: false, error: 'Ошибка соединения'})
        }
      }
    } else if (step === 1) {
      // Отправляем запрос с паролем 2FA
      if (!twoFactorPassword) {
        setReclaimDialog({...reclaimDialog, error: 'Введите пароль 2FA'})
        return
      }
      
      setReclaimDialog({...reclaimDialog, loading: true, error: ''})
      try {
        const response = await fetchWithAuth(`/api/accounts/${accountId}/reclaim/`, {
          method: 'POST',
          body: JSON.stringify({
            two_factor_password: twoFactorPassword
          })
        })
        
        const data = await response.json()
        if (data.message) {
          setReclaimDialog({...reclaimDialog, loading: false, step: 2, success: data.message})
          fetchAccounts()
        } else if (data.error) {
          setReclaimDialog({...reclaimDialog, loading: false, error: data.error})
        }
      } catch (err) {
        setReclaimDialog({...reclaimDialog, loading: false, error: 'Ошибка соединения'})
      }
    }
  }

  const handleReauthorize = (accountId, accountPhone) => {
    setReauthorizeDialog({ 
      open: true, 
      accountId, 
      accountPhone,
      step: 0,
      loading: false,
      error: '',
      success: '',
      requires2FA: false,
      verificationCode: '',
      twoFactorPassword: ''
    })
  }

  const handleStartReauthorization = async () => {
    const { accountId } = reauthorizeDialog
    setReauthorizeDialog({...reauthorizeDialog, loading: true, error: '', success: ''})
    
    try {
      const response = await fetchWithAuth(`/api/accounts/${accountId}/reauthorize/`, {
        method: 'POST'
      })
      
      const data = await response.json()
      if (data.error) {
        setReauthorizeDialog({...reauthorizeDialog, loading: false, error: data.error})
      } else {
        setReauthorizeDialog({...reauthorizeDialog, loading: false, step: 1, success: data.message})
      }
    } catch (err) {
      setReauthorizeDialog({...reauthorizeDialog, loading: false, error: 'Не удалось начать повторную авторизацию'})
    }
  }

  const handleVerifyReauthorization = async () => {
    const { accountId, verificationCode, twoFactorPassword } = reauthorizeDialog
    
    if (!verificationCode) {
      setReauthorizeDialog({...reauthorizeDialog, error: 'Введите код подтверждения'})
      return
    }
    
    setReauthorizeDialog({...reauthorizeDialog, loading: true, error: '', success: ''})
    
    try {
      const response = await fetchWithAuth(`/api/accounts/${accountId}/verify-reauthorization/`, {
        method: 'POST',
        body: JSON.stringify({
          verification_code: verificationCode,
          two_factor_password: twoFactorPassword || null
        })
      })
      
      const data = await response.json()
      if (data.error) {
        if (data.requires_2fa) {
          setReauthorizeDialog({...reauthorizeDialog, loading: false, step: 2, error: data.error, requires2FA: true})
        } else {
          setReauthorizeDialog({...reauthorizeDialog, loading: false, error: data.error})
        }
      } else {
        setReauthorizeDialog({...reauthorizeDialog, loading: false, success: data.message})
        setTimeout(() => {
          setReauthorizeDialog({ open: false, accountId: null, accountPhone: '', step: 0, loading: false, error: '', success: '', requires2FA: false, verificationCode: '', twoFactorPassword: '' })
          fetchAccounts()
        }, 2000)
      }
    } catch (err) {
      setReauthorizeDialog({...reauthorizeDialog, loading: false, error: 'Ошибка проверки кода'})
    }
  }

  const handleCheckAPICredentials = async () => {
    const { apiId, apiHash } = apiSettingsDialog
    
    if (!apiId || !apiHash) {
      setApiSettingsDialog({...apiSettingsDialog, checkResult: {isValid: false, message: 'Заполните оба поля'}})
      return
    }
    
    setApiSettingsDialog({...apiSettingsDialog, checking: true})
    
    try {
      const response = await fetchWithAuth('/api/check-api-credentials/', {
        method: 'POST',
        body: JSON.stringify({ api_id: apiId, api_hash: apiHash })
      })
      
      const data = await response.json()
      setApiSettingsDialog({...apiSettingsDialog, checking: false, checkResult: data})
    } catch (err) {
      setApiSettingsDialog({
        ...apiSettingsDialog, 
        checking: false, 
        checkResult: {isValid: false, message: 'Ошибка проверки: ' + err.message}
      })
    }
  }

  const filteredAccounts = accounts.filter(account =>
    account.phone_number?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (account.employee_id && account.employee_id.toLowerCase().includes(searchTerm.toLowerCase())) ||
    (account.employee_fio && account.employee_fio.toLowerCase().includes(searchTerm.toLowerCase()))
  )

  const StatCard = ({ title, value, icon, color }) => (
    <Card sx={{ minWidth: 200, backgroundColor: color + '.50', border: `1px solid ${color}.100` }}>
      <CardContent>
        <Box display="flex" alignItems="center" mb={1}>
          {icon}
          <Typography variant="h6" sx={{ ml: 1 }}>
            {title}
          </Typography>
        </Box>
        <Typography variant="h4" color={color + '.main'}>
          {value}
        </Typography>
      </CardContent>
    </Card>
  )

  const renderReclaimStep = () => {
    switch (reclaimDialog.step) {
      case 0:
        return (
          <Box>
            <DialogContentText>
              Вы уверены, что хотите вернуть аккаунт {reclaimDialog.accountPhone}?
              
              Это действие:
              1. Завершит ВСЕ активные сессии на всех устройствах
              2. Пытается сменить пароль (если 2FA не включено)
              3. Удалит сессию из базы данных
              4. Изменит статус аккаунта на 'возвращен'
            </DialogContentText>
            <Alert severity="warning" sx={{ mt: 2 }}>
              Это действие следует выполнять только при увольнении сотрудника. После возврата аккаунта сотрудник не сможет войти в Telegram с этого номера на любом устройстве.
            </Alert>
          </Box>
        )
      case 1:
        return (
          <Box>
            <DialogContentText>
              Для аккаунта {reclaimDialog.accountPhone} включена двухфакторная аутентификация (2FA).
              Введите пароль 2FA для завершения всех сессий и возврата аккаунта.
            </DialogContentText>
            <TextField
              autoFocus
              margin="dense"
              label="Пароль 2FA"
              type="password"
              fullWidth
              value={reclaimDialog.twoFactorPassword}
              onChange={(e) => setReclaimDialog({...reclaimDialog, twoFactorPassword: e.target.value})}
              disabled={reclaimDialog.loading}
            />
            <Alert severity="info" sx={{ mt: 2 }}>
              Без правильного пароля 2FA невозможно завершить все сессии на других устройствах.
            </Alert>
          </Box>
        )
      case 2:
        return (
          <Box>
            {reclaimDialog.success && (
              <Alert severity="success" sx={{ mb: 2 }}>
                {reclaimDialog.success}
              </Alert>
            )}
            <DialogContentText>
              Процедура возврата аккаунта завершена.
            </DialogContentText>
          </Box>
        )
      default:
        return null
    }
  }

  const renderReauthorizeStep = () => {
    switch (reauthorizeDialog.step) {
      case 0:
        return (
          <Box>
            <DialogContentText>
              Начать процесс повторной авторизации для аккаунта {reauthorizeDialog.accountPhone}?
              На номер будет отправлен новый код подтверждения.
            </DialogContentText>
          </Box>
        )
      case 1:
        return (
          <Box>
            <DialogContentText>
              Код подтверждения отправлен на номер {reauthorizeDialog.accountPhone}.
              Введите код из SMS сообщения.
            </DialogContentText>
            <TextField
              autoFocus
              margin="dense"
              label="Код подтверждения"
              fullWidth
              value={reauthorizeDialog.verificationCode}
              onChange={(e) => setReauthorizeDialog({...reauthorizeDialog, verificationCode: e.target.value})}
              disabled={reauthorizeDialog.loading}
            />
          </Box>
        )
      case 2:
        return (
          <Box>
            <DialogContentText>
              Для аккаунта {reauthorizeDialog.accountPhone} требуется пароль 2FA.
              Введите пароль двухфакторной аутентификации.
            </DialogContentText>
            <TextField
              autoFocus
              margin="dense"
              label="Пароль 2FA"
              type="password"
              fullWidth
              value={reauthorizeDialog.twoFactorPassword}
              onChange={(e) => setReauthorizeDialog({...reauthorizeDialog, twoFactorPassword: e.target.value})}
              disabled={reauthorizeDialog.loading}
            />
          </Box>
        )
      default:
        return null
    }
  }

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" mt={4}>
        <CircularProgress />
        <Typography sx={{ ml: 2 }}>Загрузка аккаунтов...</Typography>
      </Box>
    )
  }

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Панель управления Telegram аккаунтами
      </Typography>
      
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item>
          <StatCard 
            title="Всего аккаунтов" 
            value={stats.total} 
            icon={<AccountCircle color="primary" />} 
            color="primary" 
          />
        </Grid>
        <Grid item>
          <StatCard 
            title="Активные" 
            value={stats.active} 
            icon={<PhoneAndroid color="success" />} 
            color="success" 
          />
        </Grid>
        <Grid item>
          <StatCard 
            title="Ожидают" 
            value={stats.pending} 
            icon={<Description color="warning" />} 
            color="warning" 
          />
        </Grid>
        <Grid item>
          <StatCard 
            title="Возвращены" 
            value={stats.reclaimed} 
            icon={<Email color="error" />} 
            color="error" 
          />
        </Grid>
      </Grid>
      
      <Box mb={3} display="flex" justifyContent="space-between" alignItems="center">
        <TextField
          placeholder="Поиск по номеру, ID сотрудника или ФИО"
          variant="outlined"
          size="small"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <Search />
              </InputAdornment>
            )
          }}
          sx={{ width: '300px' }}
        />
        <Box>
          <Tooltip title="Проверить API настройки">
            <IconButton 
              onClick={() => setApiSettingsDialog({ open: true, apiId: '', apiHash: '', checking: false, checkResult: null })}
              sx={{ mr: 1 }}
            >
              <Settings />
            </IconButton>
          </Tooltip>
          <IconButton 
            onClick={handleRefresh} 
            disabled={refreshing}
            sx={{ mr: 2 }}
            title="Обновить список аккаунтов"
          >
            <Refresh />
          </IconButton>
          <Button
            variant="contained"
            color="primary"
            href="/add-account"
          >
            Добавить новый аккаунт
          </Button>
        </Box>
      </Box>

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Номер телефона</TableCell>
              <TableCell>ФИО сотрудника</TableCell>
              <TableCell>ID сотрудника</TableCell>
              <TableCell>Статус</TableCell>
              <TableCell>Последнее обновление</TableCell>
              <TableCell>2FA</TableCell>
              <TableCell>Действия</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {filteredAccounts.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} align="center">
                  <Typography variant="body2" color="textSecondary">
                    Аккаунты не найдены
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              filteredAccounts.map((account) => (
                <TableRow key={account.id} hover>
                  <TableCell>
                    <Box display="flex" alignItems="center">
                      <PhoneAndroid sx={{ mr: 1, color: 'text.secondary' }} />
                      {account.phone_number}
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Box display="flex" alignItems="center">
                      <AccountCircle sx={{ mr: 1, color: 'text.secondary' }} />
                      {account.employee_fio || '-'}
                    </Box>
                  </TableCell>
                  <TableCell>{account.employee_id || '-'}</TableCell>
                  <TableCell>
                    <Chip
                      label={account.account_status === 'active' ? 'Активен' : 
                             account.account_status === 'suspended' ? 'Приостановлен' : 
                             account.account_status === 'reclaimed' ? 'Возвращен' : 
                             account.account_status === 'pending' ? 'Ожидает' :
                             account.account_status === 'pending_2fa' ? 'Ожидает 2FA' :
                             account.account_status === 'pending_reauthorization' ? 'Ожидает повторной авторизации' : account.account_status}
                      color={account.account_status === 'active' ? 'success' : 
                             account.account_status === 'pending' || account.account_status === 'pending_2fa' || account.account_status === 'pending_reauthorization' ? 'warning' : 
                             account.account_status === 'reclaimed' ? 'error' : 'default'}
                      size="small"
                    />
                  </TableCell>
                  <TableCell>
                    {account.session_updated_at ? new Date(account.session_updated_at).toLocaleDateString('ru-RU') : '-'}
                  </TableCell>
                  <TableCell>
                    {account.is_2fa_enabled ? (
                      <Chip label="Включено" color="warning" size="small" />
                    ) : (
                      <Chip label="Выключено" size="small" />
                    )}
                  </TableCell>
                  <TableCell>
                    <Box display="flex" gap={1} flexWrap="wrap">
                      <Button
                        size="small"
                        variant="outlined"
                        onClick={() => handleChangePassword(account.id, account.phone_number)}
                      >
                        Сменить пароль
                      </Button>
                      <Button
                        size="small"
                        variant="outlined"
                        color="secondary"
                        onClick={() => handleAction('delete-session', account.id, account.phone_number)}
                      >
                        Удалить сессию
                      </Button>
                      <Button
                        size="small"
                        variant="outlined"
                        color="info"
                        onClick={() => handleAction('details', account.id, account.phone_number)}
                      >
                        Детали
                      </Button>
                      <Button
                        size="small"
                        variant="outlined"
                        color="warning"
                        onClick={() => handleReclaim(account.id, account.phone_number, account.is_2fa_enabled)}
                      >
                        Вернуть аккаунт
                      </Button>
                      <Button
                        size="small"
                        variant="outlined"
                        color="primary"
                        startIcon={<LockReset />}
                        onClick={() => handleReauthorize(account.id, account.phone_number)}
                        disabled={account.account_status === 'active' && !account.is_2fa_enabled}
                      >
                        Повторная авторизация
                      </Button>
                    </Box>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>

      <Dialog open={detailsDialog.open} onClose={() => setDetailsDialog({ open: false, accountId: null, accountPhone: '', details: '' })}>
        <DialogTitle>Детали аккаунта {detailsDialog.accountPhone}</DialogTitle>
        <DialogContent>
          <Box sx={{ whiteSpace: 'pre-line', fontFamily: 'monospace', padding: 2, backgroundColor: '#f5f5f5', borderRadius: 1 }}>
            {detailsDialog.details}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDetailsDialog({ open: false, accountId: null, accountPhone: '', details: '' })}>Закрыть</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={reclaimDialog.open} onClose={() => setReclaimDialog({ open: false, accountId: null, accountPhone: '', is2FAEnabled: false, twoFactorPassword: '', step: 0, loading: false, error: '', success: '' })} maxWidth="sm" fullWidth>
        <DialogTitle>
          Возврат аккаунта {reclaimDialog.accountPhone}
          {reclaimDialog.step < 2 && (
            <Stepper activeStep={reclaimDialog.step} sx={{ mt: 2 }}>
              {reclaimSteps.map((label) => (
                <Step key={label}>
                  <StepLabel>{label}</StepLabel>
                </Step>
              ))}
            </Stepper>
          )}
        </DialogTitle>
        <DialogContent>
          {reclaimDialog.error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {reclaimDialog.error}
            </Alert>
          )}
          
          {renderReclaimStep()}
        </DialogContent>
        <DialogActions>
          {reclaimDialog.step < 2 && (
            <>
              <Button 
                onClick={() => setReclaimDialog({ open: false, accountId: null, accountPhone: '', is2FAEnabled: false, twoFactorPassword: '', step: 0, loading: false, error: '', success: '' })}
              >
                Отмена
              </Button>
              <Button 
                onClick={handleReclaimStep} 
                variant="contained" 
                color="warning"
                disabled={reclaimDialog.loading}
              >
                {reclaimDialog.loading ? <CircularProgress size={24} /> : 
                 reclaimDialog.step === 1 ? 'Вернуть аккаунт' : 
                 'Продолжить'}
              </Button>
            </>
          )}
          {reclaimDialog.step === 2 && (
            <Button 
              onClick={() => setReclaimDialog({ open: false, accountId: null, accountPhone: '', is2FAEnabled: false, twoFactorPassword: '', step: 0, loading: false, error: '', success: '' })}
              variant="contained"
            >
              Закрыть
            </Button>
          )}
        </DialogActions>
      </Dialog>

      <Dialog open={passwordDialog.open} onClose={() => setPasswordDialog({ open: false, accountId: null, accountPhone: '', oldPassword: '', newPassword: '' })}>
        <DialogTitle>Смена пароля для {passwordDialog.accountPhone}</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Введите старый и новый пароль для аккаунта. Оставьте старый пароль пустым, если 2FA не включено.
          </DialogContentText>
          <TextField
            autoFocus
            margin="dense"
            label="Старый пароль (если включено 2FA)"
            type="password"
            fullWidth
            value={passwordDialog.oldPassword}
            onChange={(e) => setPasswordDialog({...passwordDialog, oldPassword: e.target.value})}
          />
          <TextField
            margin="dense"
            label="Новый пароль"
            type="password"
            fullWidth
            value={passwordDialog.newPassword}
            onChange={(e) => setPasswordDialog({...passwordDialog, newPassword: e.target.value})}
            placeholder="Оставьте пустым для пароля по умолчанию"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPasswordDialog({ open: false, accountId: null, accountPhone: '', oldPassword: '', newPassword: '' })}>Отмена</Button>
          <Button onClick={confirmChangePassword} color="primary">Сменить пароль</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={reauthorizeDialog.open} onClose={() => setReauthorizeDialog({ open: false, accountId: null, accountPhone: '', step: 0, loading: false, error: '', success: '', requires2FA: false, verificationCode: '', twoFactorPassword: '' })} maxWidth="sm" fullWidth>
        <DialogTitle>Повторная авторизация аккаунта {reauthorizeDialog.accountPhone}</DialogTitle>
        <DialogContent>
          <Stepper activeStep={reauthorizeDialog.step} sx={{ mb: 3 }}>
            {reauthorizeSteps.map((label) => (
              <Step key={label}>
                <StepLabel>{label}</StepLabel>
              </Step>
            ))}
          </Stepper>
          
          {reauthorizeDialog.error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {reauthorizeDialog.error}
            </Alert>
          )}
          
          {reauthorizeDialog.success && (
            <Alert severity="success" sx={{ mb: 2 }}>
              {reauthorizeDialog.success}
            </Alert>
          )}
          
          {renderReauthorizeStep()}
        </DialogContent>
        <DialogActions>
          <Button 
            onClick={() => setReauthorizeDialog({ open: false, accountId: null, accountPhone: '', step: 0, loading: false, error: '', success: '', requires2FA: false, verificationCode: '', twoFactorPassword: '' })}
          >
            Отмена
          </Button>
          {reauthorizeDialog.step === 0 && (
            <Button 
              onClick={handleStartReauthorization} 
              variant="contained" 
              color="primary"
              disabled={reauthorizeDialog.loading}
            >
              {reauthorizeDialog.loading ? <CircularProgress size={24} /> : 'Начать'}
            </Button>
          )}
          {(reauthorizeDialog.step === 1 || reauthorizeDialog.step === 2) && (
            <Button 
              onClick={handleVerifyReauthorization} 
              variant="contained" 
              color="primary"
              disabled={reauthorizeDialog.loading}
            >
              {reauthorizeDialog.loading ? <CircularProgress size={24} /> : 'Подтвердить'}
            </Button>
          )}
        </DialogActions>
      </Dialog>

      <Dialog open={apiSettingsDialog.open} onClose={() => setApiSettingsDialog({ open: false, apiId: '', apiHash: '', checking: false, checkResult: null })}>
        <DialogTitle>Проверка API настроек Telegram</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Введите API ID и API Hash для проверки корректности настроек.
            Получите их на <a href="https://my.telegram.org" target="_blank" rel="noopener noreferrer">my.telegram.org</a>.
          </DialogContentText>
          
          <TextField
            autoFocus
            margin="dense"
            label="API ID"
            type="number"
            fullWidth
            value={apiSettingsDialog.apiId}
            onChange={(e) => setApiSettingsDialog({...apiSettingsDialog, apiId: e.target.value})}
            sx={{ mt: 2 }}
          />
          <TextField
            margin="dense"
            label="API Hash"
            type="text"
            fullWidth
            value={apiSettingsDialog.apiHash}
            onChange={(e) => setApiSettingsDialog({...apiSettingsDialog, apiHash: e.target.value})}
          />
          
          {apiSettingsDialog.checkResult && (
            <Alert 
              severity={apiSettingsDialog.checkResult.isValid ? "success" : "error"}
              sx={{ mt: 2 }}
            >
              {apiSettingsDialog.checkResult.message}
            </Alert>
          )}
          
          <Box sx={{ mt: 2, display: 'flex', justifyContent: 'space-between' }}>
            <Button 
              variant="outlined" 
              href="/admin/accounts/globalappsettings/" 
              target="_blank"
            >
              Настроить в админке
            </Button>
            <Button 
              variant="contained" 
              onClick={handleCheckAPICredentials}
              disabled={apiSettingsDialog.checking}
            >
              {apiSettingsDialog.checking ? <CircularProgress size={24} /> : 'Проверить'}
            </Button>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setApiSettingsDialog({ open: false, apiId: '', apiHash: '', checking: false, checkResult: null })}>Закрыть</Button>
        </DialogActions>
      </Dialog>

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

export default Dashboard