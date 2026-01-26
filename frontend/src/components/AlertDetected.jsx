import React, { useState, useEffect } from 'react'
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Box,
  Typography,
  CircularProgress,
  Alert,
  Snackbar,
  Chip,
  IconButton,
  Button,
  Card,
  CardContent,
  Grid
} from '@mui/material'
import { CheckCircle, Error, Refresh, Warning, Security } from '@mui/icons-material'
import { fetchWithAuth } from '../utils'

const AlertDetected = () => {
  const [securityData, setSecurityData] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'info' })
  
  const fetchSecurityData = async () => {
    setLoading(true)
    try {
      const response = await fetchWithAuth('/api/security-alerts/')
      if (response.ok) {
        const data = await response.json()
        setSecurityData(data)
      } else {
        setError('Не удалось загрузить данные безопасности')
      }
    } catch (err) {
      console.error('Ошибка загрузки данных безопасности:', err)
      setError('Ошибка соединения с сервером')
    } finally {
      setLoading(false)
    }
  }
  
  useEffect(() => {
    fetchSecurityData()
  }, [])
  
  const handleRefresh = () => {
    fetchSecurityData()
  }
  
  const getAlertStatusIcon = (hasAlert) => {
    if (hasAlert) {
      return <Error color="error" sx={{ mr: 1 }} />
    } else {
      return <CheckCircle color="success" sx={{ mr: 1 }} />
    }
  }
  
  const getAlertStatusText = (hasAlert) => {
    if (hasAlert) {
      return 'Обнаружена попытка кражи аккаунта!'
    } else {
      return 'Безопасен'
    }
  }
  
  const getAlertStatusColor = (hasAlert) => {
    if (hasAlert) {
      return 'error'
    } else {
      return 'success'
    }
  }
  
  const countAlerts = securityData.filter(item => item.has_security_alert).length
  const totalAccounts = securityData.length
  
  if (loading) {
    return (
      <Box display="flex" justifyContent="center" mt={4}>
        <CircularProgress />
        <Typography sx={{ ml: 2 }}>Загрузка данных безопасности...</Typography>
      </Box>
    )
  }
  
  if (error) {
    return (
      <Box display="flex" justifyContent="center" mt={4}>
        <Alert severity="error" action={
          <Button color="inherit" size="small" onClick={fetchSecurityData}>
            Повторить
          </Button>
        }>
          {error}
        </Alert>
      </Box>
    )
  }
  
  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4" gutterBottom>
          <Security sx={{ mr: 2, verticalAlign: 'middle' }} />
          Мониторинг безопасности аккаунтов
        </Typography>
        <Button
          variant="outlined"
          startIcon={<Refresh />}
          onClick={handleRefresh}
        >
          Обновить
        </Button>
      </Box>
      
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography color="textSecondary" gutterBottom>
                Всего аккаунтов
              </Typography>
              <Typography variant="h4">
                {totalAccounts}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography color="textSecondary" gutterBottom>
                Безопасные аккаунты
              </Typography>
              <Typography variant="h4" color="success.main">
                {totalAccounts - countAlerts}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography color="textSecondary" gutterBottom>
                Аккаунты с угрозами
              </Typography>
              <Typography variant="h4" color="error.main">
                {countAlerts}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
      
      {countAlerts > 0 && (
        <Alert severity="warning" sx={{ mb: 3 }}>
          <Typography variant="body1">
            <strong>Внимание!</strong> Обнаружено {countAlerts} аккаунтов с признаками попытки кражи.
            Рекомендуется немедленно принять меры для защиты этих аккаунтов.
          </Typography>
        </Alert>
      )}
      
      <Paper sx={{ p: 2 }}>
        <Typography variant="h6" gutterBottom>
          Детали проверки безопасности
        </Typography>
        
        <TableContainer>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Номер телефона</TableCell>
                <TableCell>Сотрудник</TableCell>
                <TableCell>Статус безопасности</TableCell>
                <TableCell>Сообщение</TableCell>
                <TableCell>Последняя проверка</TableCell>
                <TableCell>Статус аккаунта</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {securityData.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} align="center">
                    <Typography variant="body2" color="textSecondary">
                      Нет данных о безопасности
                    </Typography>
                  </TableCell>
                </TableRow>
              ) : (
                securityData.map((item) => (
                  <TableRow key={item.id} hover>
                    <TableCell>
                      <Typography variant="body2">
                        {item.phone_number}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">
                        {item.employee_fio || '-'}
                      </Typography>
                      <Typography variant="caption" color="textSecondary">
                        {item.employee_id || ''}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Box display="flex" alignItems="center">
                        {getAlertStatusIcon(item.has_security_alert)}
                        <Chip
                          label={getAlertStatusText(item.has_security_alert)}
                          color={getAlertStatusColor(item.has_security_alert)}
                          size="small"
                        />
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" color={item.has_security_alert ? "error" : "textSecondary"}>
                        {item.alert_message || 'Нет сообщений'}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">
                        {item.last_security_check ? new Date(item.last_security_check).toLocaleString('ru-RU') : 'Не проверялся'}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={item.account_status === 'active' ? 'Активен' : 
                               item.account_status === 'reclaimed' ? 'Возвращен' : 
                               item.account_status}
                        color={item.account_status === 'active' ? 'success' : 
                               item.account_status === 'reclaimed' ? 'error' : 'default'}
                        size="small"
                      />
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>
      
      <Box mt={3}>
        <Alert severity="info">
          <Typography variant="body2">
            <strong>Похуй что-то напишу потом</strong>
          </Typography>
          <Typography variant="body2" sx={{ mt: 1 }}>
            1. Интересно
            2. А как
            3. какают
            4. бабочки?
          </Typography>
        </Alert>
      </Box>
      
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

export default AlertDetected