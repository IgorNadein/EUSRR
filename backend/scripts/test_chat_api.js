/**
 * Тестирование Chat API через Node.js
 * Запуск: node scripts/test_chat_api.js
 */

const https = require('https');
const http = require('http');

const BASE_URL = process.env.API_URL || 'http://localhost:9000';
const CHAT_ID = process.env.CHAT_ID || '10';
const SESSION_COOKIE = process.env.SESSION_COOKIE || ''; // sessionid=xxx

/**
 * Делает HTTP запрос
 */
function makeRequest(path, options = {}) {
    return new Promise((resolve, reject) => {
        const url = new URL(path, BASE_URL);
        const protocol = url.protocol === 'https:' ? https : http;
        
        const reqOptions = {
            method: options.method || 'GET',
            headers: {
                'Cookie': SESSION_COOKIE,
                'Accept': 'application/json',
                ...options.headers
            }
        };
        
        const req = protocol.request(url, reqOptions, (res) => {
            let data = '';
            res.on('data', chunk => data += chunk);
            res.on('end', () => {
                try {
                    const json = JSON.parse(data);
                    resolve({ status: res.statusCode, data: json });
                } catch (e) {
                    resolve({ status: res.statusCode, data, error: e.message });
                }
            });
        });
        
        req.on('error', reject);
        req.end();
    });
}

/**
 * Тесты
 */
async function runTests() {
    console.log('🧪 Тестирование Chat API\n');
    console.log(`Base URL: ${BASE_URL}`);
    console.log(`Chat ID: ${CHAT_ID}\n`);
    
    // Тест 1: Загрузка последних сообщений
    console.log('📥 Test 1: Загрузка последних сообщений');
    const latestResult = await makeRequest(`/api/v1/communications/chats/${CHAT_ID}/messages/`);
    console.log(`Status: ${latestResult.status}`);
    console.log(`Messages: ${latestResult.data.results?.length || 0}`);
    console.log(`Has more: ${latestResult.data.has_more}\n`);
    
    // Тест 2: Загрузка вокруг timestamp (декабрь 2025)
    const dec2025 = Date.UTC(2025, 11, 29); // 29 декабря 2025
    console.log('📅 Test 2: Загрузка вокруг даты (29 Dec 2025)');
    console.log(`Timestamp: ${dec2025} (${new Date(dec2025).toISOString()})`);
    
    const aroundResult = await makeRequest(
        `/api/v1/communications/chats/${CHAT_ID}/messages/around/?around_id=${dec2025}&limit=30`
    );
    console.log(`Status: ${aroundResult.status}`);
    console.log(`Messages: ${aroundResult.data.results?.length || 0}`);
    console.log(`Anchor ID: ${aroundResult.data.anchor_id}`);
    console.log(`Has more before: ${aroundResult.data.has_more_before}`);
    console.log(`Has more after: ${aroundResult.data.has_more_after}\n`);
    
    if (aroundResult.data.results?.length > 0) {
        console.log('Первое сообщение:');
        const first = aroundResult.data.results[0];
        console.log(`  ID: ${first.id}`);
        console.log(`  Date: ${first.created_at}`);
        console.log(`  Content: ${first.content?.substring(0, 50) || '(no content)'}...\n`);
    }
    
    // Тест 3: Загрузка истории (before_id)
    if (aroundResult.data.anchor_id) {
        console.log('⬆️  Test 3: Загрузка истории (старые сообщения)');
        const oldestId = aroundResult.data.results?.[0]?.id;
        if (oldestId) {
            const historyResult = await makeRequest(
                `/api/v1/communications/chats/${CHAT_ID}/messages/?before_id=${oldestId}&limit=20`
            );
            console.log(`Status: ${historyResult.status}`);
            console.log(`Messages: ${historyResult.data.results?.length || 0}`);
            console.log(`Has more: ${historyResult.data.has_more}\n`);
        }
    }
    
    // Тест 4: Загрузка новых (after_id)
    if (aroundResult.data.anchor_id) {
        console.log('⬇️  Test 4: Загрузка новых сообщений');
        const newestId = aroundResult.data.results?.[aroundResult.data.results.length - 1]?.id;
        if (newestId) {
            const newerResult = await makeRequest(
                `/api/v1/communications/chats/${CHAT_ID}/messages/?after_id=${newestId}&limit=20`
            );
            console.log(`Status: ${newerResult.status}`);
            console.log(`Messages: ${newerResult.data.results?.length || 0}`);
            console.log(`Has more: ${newerResult.data.has_more}\n`);
        }
    }
    
    console.log('✅ Тесты завершены');
}

// Запуск
runTests().catch(err => {
    console.error('❌ Ошибка:', err);
    process.exit(1);
});
