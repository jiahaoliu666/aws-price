import React, { useState } from 'react';
import { 
  Container, 
  Box, 
  TextField, 
  Button, 
  Typography, 
  Paper, 
  CircularProgress,
  Card,
  CardContent,
  Divider,
  Alert
} from '@mui/material';
import axios from 'axios';
import './App.css';

// API 基礎URL
const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:3001';

interface PricingData {
  instanceType: string;
  operatingSystem: string;
  region: string;
  onDemandPrice: string;
  unit: string;
}

interface QueryResult {
  query: string;
  parameters: {
    service?: string;
    region?: string;
    instance_type?: string;
    os?: string;
  };
  pricing_data: PricingData[];
  response: string;
}

function App() {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<QueryResult | null>(null);

  const handleQueryChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setQuery(event.target.value);
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    
    if (!query.trim()) {
      setError('請輸入查詢內容');
      return;
    }
    
    setLoading(true);
    setError(null);
    
    try {
      const response = await axios.post(`${API_BASE_URL}/api/query`, { query });
      setResult(response.data);
      
      // 檢查是否有價格數據
      if (response.data.pricing_data && response.data.pricing_data.length === 0) {
        setError('沒有找到符合條件的價格數據。AWS可能沒有提供該地區或配置的價格信息，或者您的查詢參數需要調整。');
      }
    } catch (err) {
      if (axios.isAxiosError(err) && err.response) {
        setError(`錯誤: ${err.response.data.error || '未知錯誤'}`);
      } else {
        setError('無法連接到服務器，請檢查後端服務是否運行');
      }
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Container maxWidth="md">
      <Box sx={{ my: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom align="center">
          AWS 價格自然語言查詢
        </Typography>
        
        <Paper 
          elevation={3} 
          sx={{ 
            p: 3, 
            mb: 4, 
            backgroundColor: '#f8f9fa' 
          }}
        >
          <Typography variant="body1" gutterBottom>
            使用自然語言查詢AWS服務價格，例如：
          </Typography>
          <Typography variant="body2" component="div" color="text.secondary">
            <ul>
              <li>東京 linux t2.micro 價格為多少</li>
              <li>AWS EC2 us-east-1 區域的 m5.xlarge Windows 執行個體每小時費用是多少</li>
              <li>新加坡區域的t3.medium Linux實例的費用</li>
            </ul>
          </Typography>
        </Paper>
        
        <Box component="form" onSubmit={handleSubmit} noValidate sx={{ mb: 4 }}>
          <TextField
            fullWidth
            label="輸入您的AWS價格查詢"
            value={query}
            onChange={handleQueryChange}
            variant="outlined"
            placeholder="例如：東京區域t2.micro的價格是多少？"
            sx={{ mb: 2 }}
          />
          <Button 
            type="submit" 
            variant="contained" 
            color="primary" 
            fullWidth 
            disabled={loading}
            sx={{ py: 1.5 }}
          >
            {loading ? <CircularProgress size={24} /> : '查詢'}
          </Button>
        </Box>
        
        {error && (
          <Alert severity="warning" sx={{ mb: 3 }}>
            {error}
          </Alert>
        )}
        
        {result && (
          <Card variant="outlined" sx={{ mb: 4 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>查詢結果</Typography>
              
              <Divider sx={{ my: 2 }} />
              
              <Typography variant="body1" sx={{ whiteSpace: 'pre-line', mb: 3 }}>
                {result.response}
              </Typography>
              
              <Typography variant="subtitle2" color="text.secondary">
                識別的參數:
              </Typography>
              <Box sx={{ p: 1, bgcolor: '#f5f5f5', borderRadius: 1, mb: 2 }}>
                <pre style={{ margin: 0, overflow: 'auto' }}>
                  {JSON.stringify(result.parameters, null, 2)}
                </pre>
              </Box>
              
              {result.pricing_data && result.pricing_data.length > 0 && !('error' in result.pricing_data) && (
                <>
                  <Typography variant="subtitle2" color="text.secondary">
                    詳細價格數據:
                  </Typography>
                  <Box sx={{ p: 1, bgcolor: '#f5f5f5', borderRadius: 1 }}>
                    <pre style={{ margin: 0, overflow: 'auto' }}>
                      {JSON.stringify(result.pricing_data, null, 2)}
                    </pre>
                  </Box>
                </>
              )}
              
              {result.pricing_data && result.pricing_data.length === 0 && (
                <Alert severity="info" sx={{ mt: 2 }}>
                  沒有找到符合條件的價格數據。這可能是因為AWS沒有提供該配置的價格信息，或者參數組合不正確。
                </Alert>
              )}
            </CardContent>
          </Card>
        )}
      </Box>
    </Container>
  );
}

export default App;
