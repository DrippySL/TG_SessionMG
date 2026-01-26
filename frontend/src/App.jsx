import React, { useState, useEffect } from 'react'
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
  useNavigate
} from 'react-router-dom'
import {
  Container,
  AppBar,
  Toolbar,
  Typography,
  Button,
  Box,
  CircularProgress
} from '@mui/material'
import Dashboard from './components/Dashboard'
import AddAccount from './components/AddAccount'
import AlertDetected from './components/AlertDetected'
import { getCSRFToken, fetchWithAuth } from './utils'

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [isSuperuser, setIsSuperuser] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [username, setUsername] = useState('')

  const checkAuth = async () => {
    try {
      // Сначала получаем CSRF токен
      await fetch('/api/auth/csrf/', {
        credentials: 'include',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json'
        }
      });
      
      // Затем проверяем статус аутентификации
      const response = await fetchWithAuth('/api/auth/check/');
      if (response.ok) {
        const data = await response.json();
        setIsAuthenticated(data.is_authenticated)
        setIsSuperuser(data.is_superuser)
        setUsername(data.username || '')
      } else {
        setIsAuthenticated(false)
        setIsSuperuser(false)
      }
    } catch (error) {
      console.error('Ошибка проверки аутентификации:', error)
      setIsAuthenticated(false)
      setIsSuperuser(false)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    checkAuth()
    
    // Периодическая проверка аутентификации каждые 5 минут
    const interval = setInterval(checkAuth, 300000)
    
    return () => clearInterval(interval)
  }, [])

  const handleLogout = async () => {
    try {
      await fetchWithAuth('/admin/logout/', {
        method: 'POST'
      });
      setIsAuthenticated(false)
      setIsSuperuser(false)
      setUsername('')
      window.location.href = '/admin/login/?next=/'
    } catch (error) {
      window.location.href = '/admin/login/?next=/'
    }
  }

  if (isLoading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="100vh">
        <CircularProgress />
        <Typography sx={{ ml: 2 }}>Проверка аутентификации...</Typography>
      </Box>
    )
  }

  if (!isAuthenticated || !isSuperuser) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="100vh">
        <Box textAlign="center">
          <Typography variant="h6" gutterBottom>
            Требуется аутентификация
          </Typography>
          <Typography variant="body2" gutterBottom>
            Для доступа к системе необходимо войти как суперпользователь.
          </Typography>
          <Button 
            variant="contained" 
            color="primary" 
            href="/admin/login/?next=/"
            sx={{ mt: 2 }}
          >
            Перейти к входу
          </Button>
        </Box>
      </Box>
    )
  }

  return (
    <Router>
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            Система управления Telegram аккаунтами
          </Typography>
          {username && (
            <Typography variant="body2" sx={{ mr: 2 }}>
              Вход выполнен: {username}
            </Typography>
          )}
          <Button color="inherit" href="/dashboard">Панель управления</Button>
          <Button color="inherit" href="/add-account">Добавить аккаунт</Button>
          <Button color="inherit" href="/alert-detected">Мониторинг безопасности</Button>
          <Button color="inherit" onClick={handleLogout}>Выйти</Button>
        </Toolbar>
      </AppBar>
      <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
        <Routes>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/add-account" element={<AddAccount />} />
          <Route path="/alert-detected" element={<AlertDetected />} />
          <Route path="/" element={<Navigate to="/dashboard" />} />
        </Routes>
      </Container>
    </Router>
  )
}