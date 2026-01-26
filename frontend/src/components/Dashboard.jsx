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
  StepLabel,
  Checkbox,
  LinearProgress,
  FormControlLabel,
  MenuItem,
  Select,
  FormControl,
  InputLabel
} from '@mui/material'
import { Search, Refresh, AccountCircle, PhoneAndroid, Email, Description, Settings, LockReset, CheckCircle, Error, Schedule, PlayArrow, Stop, FilterList, Clear, Edit } from '@mui/icons-material'
import { fetchWithAuth } from '../utils'

const Dashboard = () => {
  const [accounts, setAccounts] = useState([])
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedAccounts, setSelectedAccounts] = useState([])
  const [bulkActionLoading, setBulkActionLoading] = useState(false)
  
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
  const [stats, setStats] = useState({ total: 0, active: 0, pending: 0, reclaimed: 0, dead: 0, flood: 0 })
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
  
  const [tasks, setTasks] = useState([])
  const [tasksLoading, setTasksLoading] = useState(false)
  const [activeTasks, setActiveTasks] = useState(0)
  const [bulkActionDialog, setBulkActionDialog] = useState({ open: false, action: 'check' })
  
  const [accountStatusFilter, setAccountStatusFilter] = useState('')
  const [activityStatusFilter, setActivityStatusFilter] = useState('')
  const [lastPingFromFilter, setLastPingFromFilter] = useState('')
  const [lastPingToFilter, setLastPingToFilter] = useState('')
  
  const [editDialog, setEditDialog] = useState({ 
    open: false, 
    accountId: null, 
    accountPhone: '', 
    employee_fio: '', 
    employee_id: '', 
    account_note: '',
    loading: false, 
    error: '', 
    success: '' 
  })
  
  const reclaimSteps = ['Подтверждение', 'Ввод пароля 2FA', 'Завершение']
  const reauthorizeSteps = ['Отправка кода', 'Ввод кода подтверждения', 'Ввод пароля 2FA (если требуется)']

  const fetchAccounts = async () => {
    setLoading(true)
    try {
      let url = '/api/accounts/'
      const params = new URLSearchParams()
      if (searchTerm) params.append('search', searchTerm)
      if (accountStatusFilter) params.append('status', accountStatusFilter)
      if (activityStatusFilter) params.append('activity_status', activityStatusFilter)
      if (lastPingFromFilter) params.append('last_ping_from', lastPingFromFilter)
      if (lastPingToFilter) params.append('last_ping_to', lastPingToFilter)
      
      if (params.toString()) {
        url += '?' + params.toString()
      }
      
      const response = await fetchWithAuth(url)
      if (response.ok) {
        const data = await response.json()
        setAccounts(data)
        
        const total = data.length
        const active = data.filter(a => a.account_status === 'active').length
        const pending = data.filter(a => a.account_status === 'pending' || a.account_status === 'pending_2fa' || a.account_status === 'pending_reauthorization').length
        const reclaimed = data.filter(a => a.account_status === 'reclaimed').length
        const dead = data.filter(a => a.activity_status === 'dead').length
        const flood = data.filter(a => a.activity_status === 'flood').length
        
        setStats({ total, active, pending, reclaimed, dead, flood })
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
        message: 'Не удалось загрузить аккаунтов. Проверьте подключение к бэкенду.',
        severity: 'error'
      })
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }
  
  const fetchTasks = async () => {
    setTasksLoading(true)
    try {
      const response = await fetchWithAuth('/api/tasks/?status=processing')
      if (response.ok) {
        const data = await response.json()
        setTasks(data)
        setActiveTasks(data.filter(t => t.status === 'processing').length)
      }
    } catch (err) {
      console.error('Ошибка загрузки задач:', err)
    } finally {
      setTasksLoading(false)
    }
  }

  useEffect(() => {
    fetchAccounts()
    fetchTasks()
    
    const interval = setInterval(fetchTasks, 10000)
    return () => clearInterval(interval)
  }, [])

  const handleRefresh = () => {
    setRefreshing(true)
    fetchAccounts()
    fetchTasks()
  }
  
  const handleFilterChange = () => {
    setSelectedAccounts([])
    fetchAccounts()
  }
  
  const handleResetFilters = () => {
    setSearchTerm('')
    setAccountStatusFilter('')
    setActivityStatusFilter('')
    setLastPingFromFilter('')
    setLastPingToFilter('')
    setSelectedAccounts([])
    fetchAccounts()
  }

  const handleSelectAccount = (accountId) => {
    setSelectedAccounts(prev => {
      if (prev.includes(accountId)) {
        return prev.filter(id => id !== accountId)
      } else {
        return [...prev, accountId]
      }
    })
  }

  const handleSelectAll = () => {
    if (selectedAccounts.length === filteredAccounts.length) {
      setSelectedAccounts([])
    } else {
      setSelectedAccounts(filteredAccounts.map(a => a.id))
    }
  }

  const handleBulkAction = async (action) => {
    if (selectedAccounts.length === 0) {
      setSnackbar({
        open: true,
        message: 'Выберите хотя бы один аккаунт',
        severity: 'warning'
      })
      return
    }
    
    setBulkActionLoading(true)
    try {
      const response = await fetchWithAuth('/api/tasks/bulk-action/', {
        method: 'POST',
        body: JSON.stringify({
          account_ids: selectedAccounts,
          action: action
        })
      })
      
      const data = await response.json()
      if (response.ok) {
        setSnackbar({
          open: true,
          message: data.message,
          severity: 'success'
        })
        setSelectedAccounts([])
        fetchTasks()
      } else {
        setSnackbar({
          open: true,
          message: data.error || 'Ошибка выполнения групповой операции',
          severity: 'error'
        })
      }
    } catch (err) {
      setSnackbar({
        open: true,
        message: 'Ошибка соединения',
        severity: 'error'
      })
    } finally {
      setBulkActionLoading(false)
      setBulkActionDialog({ open: false, action: 'check' })
    }
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
      if (reclaimDialog.is2FAEnabled) {
        setReclaimDialog({...reclaimDialog, step: 1})
      } else {
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
            fetchTasks()
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
          fetchTasks()
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
        fetchTasks()
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

  const handleEditAccount = (accountId, accountPhone, employee_fio, employee_id, account_note) => {
    setEditDialog({ 
      open: true, 
      accountId, 
      accountPhone, 
      employee_fio: employee_fio || '', 
      employee_id: employee_id || '', 
      account_note: account_note || '',
      loading: false, 
      error: '', 
      success: '' 
    })
  }

  const handleSaveEdit = async () => {
    const { accountId, employee_fio, employee_id, account_note } = editDialog
    
    if (!employee_fio.trim() && !employee_id.trim()) {
      setEditDialog({...editDialog, error: 'Заполните хотя бы одно поле'})
      return
    }
    
    setEditDialog({...editDialog, loading: true, error: '', success: ''})
    
    try {
      const response = await fetchWithAuth(`/api/accounts/${accountId}/edit/`, {
        method: 'POST',
        body: JSON.stringify({
          employee_fio: employee_fio.trim(),
          employee_id: employee_id.trim(),
          account_note: account_note.trim()
        })
      })
      
      const data = await response.json()
      if (response.ok) {
        setEditDialog({...editDialog, loading: false, success: data.message})
        fetchAccounts()
        setTimeout(() => {
          setEditDialog({ open: false, accountId: null, accountPhone: '', employee_fio: '', employee_id: '', account_note: '', loading: false, error: '', success: '' })
        }, 2000)
      } else {
        setEditDialog({...editDialog, loading: false, error: data.error})
      }
    } catch (err) {
      setEditDialog({...editDialog, loading: false, error: 'Ошибка соединения'})
    }
  }

  const filteredAccounts = accounts

  const StatCard = ({ title, value, icon, color, subtitle }) => (
    <Card sx={{ minWidth: 180, backgroundColor: color + '.50', border: `1px solid ${color}.100` }}>
      <CardContent>
        <Box display="flex" alignItems="center" mb={1}>
          {icon}
          <Typography variant="h6" sx={{ ml: 1, fontSize: '1rem' }}>
            {title}
          </Typography>
        </Box>
        <Typography variant="h4" color={color + '.main'}>
          {value}
        </Typography>
        {subtitle && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            {subtitle}
          </Typography>
        )}
      </CardContent>
    </Card>
  )
  
  const HealthIndicator = ({ health }) => {
    const colors = {
      'green': '#4caf50',
      'yellow': '#ff9800',
      'red': '#f44336',
      'gray': '#9e9e9e'
    }
    
    return (
      <Box 
        sx={{ 
          width: 12, 
          height: 12, 
          borderRadius: '50%', 
          backgroundColor: colors[health] || colors.gray,
          display: 'inline-block',
          marginRight: 1
        }} 
      />
    )
  }

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
      
      {activeTasks > 0 && (
        <Alert 
          severity="info" 
          sx={{ mb: 3 }}
          action={
            <Button color="inherit" size="small" onClick={fetchTasks}>
              Обновить
            </Button>
          }
        >
          <Box display="flex" alignItems="center" justifyContent="space-between" width="100%">
            <Typography>
              Активные задачи: {activeTasks}
            </Typography>
            <Box sx={{ width: '200px', ml: 2 }}>
              {tasks.map(task => (
                <Box key={task.id} sx={{ mb: 1 }}>
                  <Typography variant="body2">
                    {task.task_type === 'bulk_check' ? 'Групповая проверка' : 
                     task.task_type === 'reauthorize' ? 'Повторная авторизация' : 
                     task.task_type === 'reclaim' ? 'Возврат аккаунта' : task.task_type}
                  </Typography>
                  <LinearProgress 
                    variant="determinate" 
                    value={task.progress} 
                    sx={{ height: 6, borderRadius: 3 }}
                  />
                  <Typography variant="caption" color="text.secondary">
                    {task.progress}%
                  </Typography>
                </Box>
              ))}
            </Box>
          </Box>
        </Alert>
      )}
      
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
            icon={<CheckCircle color="success" />} 
            color="success" 
            subtitle={`${stats.dead} неактивных`}
          />
        </Grid>
        <Grid item>
          <StatCard 
            title="Ожидают" 
            value={stats.pending} 
            icon={<Schedule color="warning" />} 
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
        <Grid item>
          <StatCard 
            title="Flood Wait" 
            value={stats.flood} 
            icon={<Error color="info" />} 
            color="info" 
          />
        </Grid>
      </Grid>
      
      {selectedAccounts.length > 0 && (
        <Paper sx={{ p: 2, mb: 3, backgroundColor: 'primary.light', color: 'primary.contrastText' }}>
          <Box display="flex" alignItems="center" justifyContent="space-between">
            <Typography>
              Выбрано аккаунтов: {selectedAccounts.length}
            </Typography>
            <Box>
              <Button 
                variant="contained" 
                color="secondary" 
                size="small" 
                sx={{ mr: 1 }}
                onClick={() => setBulkActionDialog({ open: true, action: 'check' })}
                disabled={bulkActionLoading}
                startIcon={<PlayArrow />}
              >
                {bulkActionLoading ? <CircularProgress size={20} /> : 'Запустить проверку'}
              </Button>
              <Button 
                variant="outlined" 
                color="inherit" 
                size="small"
                onClick={() => setSelectedAccounts([])}
              >
                Сбросить
              </Button>
            </Box>
          </Box>
        </Paper>
      )}
      
      <Paper sx={{ p: 2, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          Фильтры
        </Typography>
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} sm={6} md={3}>
            <TextField
              fullWidth
              label="Поиск"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <Search />
                  </InputAdornment>
                )
              }}
              size="small"
            />
          </Grid>
          <Grid item xs={12} sm={6} md={2}>
            <FormControl fullWidth size="small">
              <InputLabel>Статус аккаунта</InputLabel>
              <Select
                value={accountStatusFilter}
                label="Статус аккаунта"
                onChange={(e) => setAccountStatusFilter(e.target.value)}
              >
                <MenuItem value="">Все</MenuItem>
                <MenuItem value="active">Активен</MenuItem>
                <MenuItem value="pending">Ожидает</MenuItem>
                <MenuItem value="pending_2fa">Ожидает 2FA</MenuItem>
                <MenuItem value="pending_reauthorization">Ожидает повторной авторизации</MenuItem>
                <MenuItem value="suspended">Приостановлен</MenuItem>
                <MenuItem value="reclaimed">Возвращен</MenuItem>
                <MenuItem value="dead">Неактивен</MenuItem>
                <MenuItem value="flood">Flood Wait</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} sm={6} md={2}>
            <FormControl fullWidth size="small">
              <InputLabel>Статус активности</InputLabel>
              <Select
                value={activityStatusFilter}
                label="Статус активности"
                onChange={(e) => setActivityStatusFilter(e.target.value)}
              >
                <MenuItem value="">Все</MenuItem>
                <MenuItem value="active">Активен</MenuItem>
                <MenuItem value="dead">Неактивен</MenuItem>
                <MenuItem value="flood">Flood Wait</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} sm={6} md={2}>
            <TextField
              fullWidth
              label="Активность с"
              type="date"
              value={lastPingFromFilter}
              onChange={(e) => setLastPingFromFilter(e.target.value)}
              InputLabelProps={{ shrink: true }}
              size="small"
            />
          </Grid>
          <Grid item xs={12} sm={6} md={2}>
            <TextField
              fullWidth
              label="Активность по"
              type="date"
              value={lastPingToFilter}
              onChange={(e) => setLastPingToFilter(e.target.value)}
              InputLabelProps={{ shrink: true }}
              size="small"
            />
          </Grid>
          <Grid item xs={12} sm={6} md={1}>
            <Button
              fullWidth
              variant="contained"
              color="primary"
              onClick={handleFilterChange}
              startIcon={<FilterList />}
            >
              Применить
            </Button>
          </Grid>
          <Grid item xs={12} sm={6} md={1}>
            <Button
              fullWidth
              variant="outlined"
              onClick={handleResetFilters}
              startIcon={<Clear />}
            >
              Сбросить
            </Button>
          </Grid>
        </Grid>
      </Paper>
      
      <Box mb={3} display="flex" justifyContent="space-between" alignItems="center">
        <Typography variant="h6">
          Список аккаунтов
        </Typography>
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
              <TableCell padding="checkbox">
                <Checkbox
                  indeterminate={selectedAccounts.length > 0 && selectedAccounts.length < filteredAccounts.length}
                  checked={filteredAccounts.length > 0 && selectedAccounts.length === filteredAccounts.length}
                  onChange={handleSelectAll}
                />
              </TableCell>
              <TableCell>Номер телефона</TableCell>
              <TableCell>ФИО сотрудника</TableCell>
              <TableCell>ID сотрудника</TableCell>
              <TableCell>Статус</TableCell>
              <TableCell>Активность</TableCell>
              <TableCell>Последняя активность</TableCell>
              <TableCell>2FA</TableCell>
              <TableCell>Действия</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {filteredAccounts.length === 0 ? (
              <TableRow>
                <TableCell colSpan={9} align="center">
                  <Typography variant="body2" color="textSecondary">
                    Аккаунты не найдены
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              filteredAccounts.map((account) => (
                <TableRow key={account.id} hover selected={selectedAccounts.includes(account.id)}>
                  <TableCell padding="checkbox">
                    <Checkbox
                      checked={selectedAccounts.includes(account.id)}
                      onChange={() => handleSelectAccount(account.id)}
                    />
                  </TableCell>
                  <TableCell>
                    <Box display="flex" alignItems="center">
                      <HealthIndicator health={account.health_indicator} />
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
                    <Chip
                      label={account.activity_status === 'active' ? 'Активен' : 
                             account.activity_status === 'dead' ? 'Неактивен' : 
                             account.activity_status === 'flood' ? 'Flood Wait' : account.activity_status}
                      color={account.activity_status === 'active' ? 'success' : 
                             account.activity_status === 'dead' ? 'error' : 
                             account.activity_status === 'flood' ? 'warning' : 'default'}
                      size="small"
                    />
                  </TableCell>
                  <TableCell>
                    {account.last_ping ? new Date(account.last_ping).toLocaleDateString('ru-RU') : '-'}
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
                        startIcon={<Edit />}
                        onClick={() => handleEditAccount(account.id, account.phone_number, account.employee_fio, account.employee_id, account.account_note)}
                      >
                        Редактировать
                      </Button>
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

      <Dialog open={editDialog.open} onClose={() => setEditDialog({ open: false, accountId: null, accountPhone: '', employee_fio: '', employee_id: '', account_note: '', loading: false, error: '', success: '' })} maxWidth="sm" fullWidth>
        <DialogTitle>
          Редактирование аккаунта {editDialog.accountPhone}
        </DialogTitle>
        <DialogContent>
          {editDialog.error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {editDialog.error}
            </Alert>
          )}
          
          {editDialog.success && (
            <Alert severity="success" sx={{ mb: 2 }}>
              {editDialog.success}
            </Alert>
          )}
          
          <DialogContentText sx={{ mb: 2 }}>
            Измените данные сотрудника для этого аккаунта.
          </DialogContentText>
          
          <TextField
            autoFocus
            margin="dense"
            label="ФИО сотрудника"
            fullWidth
            value={editDialog.employee_fio}
            onChange={(e) => setEditDialog({...editDialog, employee_fio: e.target.value})}
            disabled={editDialog.loading}
          />
          <TextField
            margin="dense"
            label="ID сотрудника"
            fullWidth
            value={editDialog.employee_id}
            onChange={(e) => setEditDialog({...editDialog, employee_id: e.target.value})}
            disabled={editDialog.loading}
          />
          <TextField
            margin="dense"
            label="Примечание"
            fullWidth
            multiline
            rows={3}
            value={editDialog.account_note}
            onChange={(e) => setEditDialog({...editDialog, account_note: e.target.value})}
            disabled={editDialog.loading}
          />
        </DialogContent>
        <DialogActions>
          <Button 
            onClick={() => setEditDialog({ open: false, accountId: null, accountPhone: '', employee_fio: '', employee_id: '', account_note: '', loading: false, error: '', success: '' })}
            disabled={editDialog.loading}
          >
            Отмена
          </Button>
          <Button 
            onClick={handleSaveEdit} 
            variant="contained" 
            color="primary"
            disabled={editDialog.loading}
          >
            {editDialog.loading ? <CircularProgress size={24} /> : 'Сохранить'}
          </Button>
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

      <Dialog open={bulkActionDialog.open} onClose={() => setBulkActionDialog({ open: false, action: 'check' })}>
        <DialogTitle>Групповая операция</DialogTitle>
        <DialogContent>
          <DialogContentText sx={{ mb: 2 }}>
            Выбрано аккаунтов: {selectedAccounts.length}
          </DialogContentText>
          
          <FormControl fullWidth sx={{ mb: 2 }}>
            <InputLabel>Действие</InputLabel>
            <Select
              value={bulkActionDialog.action}
              label="Действие"
              onChange={(e) => setBulkActionDialog({...bulkActionDialog, action: e.target.value})}
            >
              <MenuItem value="check">Проверка аккаунтов</MenuItem>
              <MenuItem value="reauthorize" disabled>Повторная авторизация</MenuItem>
              <MenuItem value="reclaim" disabled>Возврат аккаунтов</MenuItem>
            </Select>
          </FormControl>
          
          <Alert severity="info">
            Аккаунты будут проверены в фоновом режиме с анти-флуд задержками.
            Прогресс можно отслеживать в панели мониторинга.
          </Alert>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setBulkActionDialog({ open: false, action: 'check' })}>Отмена</Button>
          <Button 
            onClick={() => handleBulkAction(bulkActionDialog.action)}
            variant="contained"
            color="primary"
            disabled={bulkActionLoading}
          >
            {bulkActionLoading ? <CircularProgress size={24} /> : 'Запустить'}
          </Button>
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