// ═══════════════════════════════
// НАСТРОЙКИ
// ═══════════════════════════════

const API_URL = '';  // На сервере API доступен по тому же домену
let currentUser = null;
let currentOrderForReview = null;
let currentRating = 0;
let currentView = 'my';
let currentRegisterRole = null;
let previousScreen = 'screen-role';
let notificationsEnabled = false;
let notificationsList = [];


// ═══════════════════════════════
// ЭКРАНЫ
// ═══════════════════════════════

function goTo(screenId) {
    document.querySelectorAll('.screen').forEach(s => {
        s.classList.remove('active');
        s.style.display = 'none';
    });
    const screen = document.getElementById(screenId);
    if (screen) {
        screen.classList.add('active');
        screen.style.display = 'flex';
    }
    previousScreen = screenId;
}

function goBack() {
    if (chatTimer) {
        clearInterval(chatTimer);
        chatTimer = null;
    }

    if (currentUser) {
        if (currentUser.role === 'customer' || currentUser.role === 'admin') {
            goTo('screen-customer-menu');
        } else {
            goTo('screen-executor-menu');
        }
    } else {
        goTo('screen-role');
    }
}


// ═══════════════════════════════
// УВЕДОМЛЕНИЯ
// ═══════════════════════════════

function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast toast-${type}`;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 4000);
}


// ═══════════════════════════════
// API-ЗАПРОСЫ
// ═══════════════════════════════

async function api(method, path, body = null, params = null) {
    let url = `${API_URL}${path}`;
    if (params) url += '?' + new URLSearchParams(params);
    const options = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) options.body = JSON.stringify(body);
    try {
        const resp = await fetch(url, options);
        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.detail || 'Ошибка');
        }
        return await resp.json();
    } catch (e) {
        showToast(e.message, 'error');
        return null;
    }
}


// ═══════════════════════════════
// ВХОД
// ═══════════════════════════════

function enterAs(role) {
    // Очищаем поля входа
    if (role === 'customer') {
        document.getElementById('login-customer').value = '';
        document.getElementById('password-customer').value = '';
    } else {
        document.getElementById('login-executor').value = '';
        document.getElementById('password-executor').value = '';
    }

    const savedUserId = localStorage.getItem(`${role}_userId`);
    if (savedUserId) {
        api('GET', '/auth/me', null, { user_id: savedUserId }).then(data => {
            if (data && data.user_id && !data.is_blocked && (data.role === role || data.role === 'admin')) {
                currentUser = data;
                goToMenu();
            } else {
                // Ошибка — сбрасываем сохранённого пользователя
                localStorage.removeItem(`${role}_userId`);
                goTo(role === 'customer' ? 'screen-reg-customer' : 'screen-reg-executor');
            }
        }).catch(() => {
            // Ошибка сети — тоже сбрасываем и показываем форму входа
            localStorage.removeItem(`${role}_userId`);
            goTo(role === 'customer' ? 'screen-reg-customer' : 'screen-reg-executor');
        });
    } else {
        goTo(role === 'customer' ? 'screen-reg-customer' : 'screen-reg-executor');
    }
}

async function loginCustomer() {
    await doLogin('customer', 'login-customer', 'password-customer');
}

async function loginExecutor() {
    await doLogin('executor', 'login-executor', 'password-executor');
}

async function doLogin(role, loginId, passwordId) {
    const login = document.getElementById(loginId).value.trim();
    const password = document.getElementById(passwordId).value.trim();
    if (!login || !password) { showToast('Введите логин и пароль', 'error'); return; }

    const data = await api('POST', '/auth/login', { login, password });
    if (data && data.user_id && (data.role === role || data.role === 'admin')) {
        currentUser = data;
        localStorage.setItem(`${role}_userId`, data.user_id);
        goToMenu();
        showToast(`Добро пожаловать, ${data.full_name}!`, 'success');
    }
}

function goToMenu() {
    if (!currentUser || !currentUser.user_id) {
        showToast('Ошибка авторизации. Войдите заново.', 'error');
        goTo('screen-role');
        return;
    }

    if (currentUser.role === 'customer' || currentUser.role === 'admin') {
        document.getElementById('customer-greeting').textContent = `Привет, ${currentUser.full_name}!`;
        goTo('screen-customer-menu');
    } else {
        document.getElementById('executor-greeting').textContent = `Привет, ${currentUser.full_name}!`;
        goTo('screen-executor-menu');
    }
}

async function showInfo() {
    const container = document.getElementById('orders-list');
    container.innerHTML = `
        <div class="card">
            <p><b>📋 Правовая информация</b></p>
            <p><b>Компания:</b> ИП Боклогов Виктор Сергеевич</p>
            <p><b>ИНН:</b> 366411567530</p>
            <p><b>ОГРНИП:</b> 326366800068466</p>
            <p><b>Адрес:</b> г. Воронеж, ул. лет.Щербакова, д. 31</p>
            <hr>
            <p>Платформа для связи заказчиков и исполнителей. Пользователи могут создавать заказы на любые услуги, не запрещённые законодательством РФ.</p>
            <p>Минимальная сумма заказа — 100 рублей.</p>
            <p>Возврат предоплаты при отмене заказа до его выполнения.</p>
            <p>Комиссия платформы: 2.4% (с учётом эквайринга — не более 5%).</p>
            <p>Чеки формируются автоматически.</p>
        </div>

        <div class="card">
            <p><b>💳 Принимаем к оплате</b></p>
            <div style="display:flex;gap:12px;align-items:center;margin:12px 0;">
                <img src="https://cdn.cloudpayments.ru/images/visa-logo.svg" alt="Visa" style="height:30px;">
                <img src="https://cdn.cloudpayments.ru/images/mastercard-logo.svg" alt="Mastercard" style="height:30px;">
                <img src="https://cdn.cloudpayments.ru/images/mir-logo.svg" alt="МИР" style="height:30px;">
            </div>
            <p style="font-size:0.8rem;color:#8b6b4b;">Платёжный партнёр: Т-Банк (T-Pay), агрегатор CloudPayments</p>
        </div>
        <div class="card">
            <p><b>🛡️ Безопасная сделка (ЮKassa)</b></p>
            <p>Платформа использует сервис «Безопасная сделка» от ЮKassa.</p>
            <p>Деньги заказчика замораживаются на счёте ЮKassa до подтверждения выполнения заказа.</p>
            <p>Платформа получает только комиссию 2.4%.</p>
            <p>Срок заморозки — до 30 дней.</p>
            <p>При отмене — возврат заказчику. При выполнении — выплата исполнителю.</p>
            <p style="font-size:0.8rem;color:#8b6b4b;">ЮKassa гарантирует сохранность средств.</p>
        </div>
        <div class="card">
            <p><b>📦 Каталог услуг</b></p>
            <p style="font-size:0.85rem;color:#8b6b4b;">Примеры услуг с фиксированными ценами:</p>
            <div style="margin-top:8px;">
                <p>🔧 Мелкий ремонт (1 час) — <b>500 ₽</b></p>
                <p>📚 Репетиторство (1 занятие) — <b>800 ₽</b></p>
                <p>🐕 Передержка животных (1 день) — <b>400 ₽</b></p>
                <p>🚗 Доставка по городу — <b>350 ₽</b></p>
                <p>🧹 Клининг (1 час) — <b>600 ₽</b></p>
                <p>💅 Маникюр — <b>1 200 ₽</b></p>
            </div>
            <p style="font-size:0.8rem;color:#8b6b4b;margin-top:8px;">Цены устанавливаются исполнителями при создании заказа. Выше приведены примеры.</p>
        </div>
        <div class="card">
            <p><b>📞 Контакты</b></p>
            <p>Email поддержки: <a href="mailto:matematika1110@gmail.com" style="color:#cd7f32;">matematika1110@gmail.com</a></p>
            <p>Telegram: <a href="https://t.me/ipartnyor" style="color:#cd7f32;">@ipartnyor</a></p>
        </div>

        <div class="card">
            <p><b>📄 Документы</b></p>
            <button class="btn btn-outline btn-sm" onclick="loadDocument('oferta')">📜 Публичная оферта</button>
            <button class="btn btn-outline btn-sm" style="margin-top:8px;" onclick="loadDocument('privacy')">🔒 Политика конфиденциальности</button>
            <div id="document-content" style="margin-top:12px;"></div>
        </div>
    `;
    goTo('screen-orders');
}

async function loadDocument(type) {
    const url = type === 'oferta' ? '/info/oferta' : '/info/privacy';
    const data = await api('GET', url);
    if (!data) return;

    const container = document.getElementById('document-content');
    container.innerHTML = `
        <div class="card" style="margin-top:12px;">
            <p><b>${data.title}</b></p>
            <p style="white-space:pre-wrap;font-size:0.85rem;">${data.text}</p>
        </div>
    `;
    container.scrollIntoView({ behavior: 'smooth' });
}
// ═══════════════════════════════
// РЕГИСТРАЦИЯ
// ═══════════════════════════════

function showRegisterForm(role) {
    currentRegisterRole = role;
    document.getElementById('register-title').textContent =
        role === 'customer' ? 'Регистрация заказчика' : 'Регистрация исполнителя';
    document.getElementById('reg-executor-fields').style.display =
        role === 'executor' ? 'block' : 'none';
    document.getElementById('reg-submit-btn').className =
        role === 'customer' ? 'btn btn-primary' : 'btn btn-secondary';

    // Очищаем поля
    ['reg-name', 'reg-phone', 'reg-login', 'reg-password', 'reg-inn', 'reg-card'].forEach(id => {
        document.getElementById(id).value = '';
    });

    goTo('screen-register');
}

async function submitRegister() {
    const name = document.getElementById('reg-name').value.trim();
    const phone = document.getElementById('reg-phone').value.trim() || 'не указан';
    const login = document.getElementById('reg-login').value.trim();
    const password = document.getElementById('reg-password').value.trim();

    if (!name || !login || !password) {
        showToast('Заполните имя, логин и пароль', 'error');
        return;
    }
    if (password.length < 4) {
        showToast('Пароль минимум 4 символа', 'error');
        return;
    }
    if (currentRegisterRole === 'executor' && !document.getElementById('reg-agreement').checked) {
        showToast('Подтвердите согласие с условиями', 'error');
        return;
    }


    const body = {
        full_name: name,
        phone,
        role: currentRegisterRole,
        login,
        password
    };

    if (currentRegisterRole === 'executor') {
        body.inn = document.getElementById('reg-inn').value.trim();
        body.card_number = document.getElementById('reg-card').value.trim();
        if (!body.inn) { showToast('Введите ИНН', 'error'); return; }
    }

    const data = await api('POST', '/auth/register', body);
    if (data && data.user_id) {
        currentUser = data;
        localStorage.setItem(`${currentRegisterRole}_userId`, data.user_id);
        goToMenu();
        showToast('Регистрация успешна!', 'success');
    }
}

function togglePassword(id) {
    const input = document.getElementById(id);
    input.type = input.type === 'password' ? 'text' : 'password';
}


// ═══════════════════════════════
// СОЗДАНИЕ ЗАКАЗА
// ═══════════════════════════════

async function createOrder() {
    const description = document.getElementById('order-description').value.trim();
    const amount = parseFloat(document.getElementById('order-amount').value);
    if (!description || !amount || amount <= 0) {
        showToast('Введите описание и сумму', 'error'); return;
    }

    const orderData = await api('POST', '/orders/create', {
        customer_id: currentUser.user_id,
        description, amount,
        secret_code: document.getElementById('order-secret').value.trim() || null
    });
    if (!orderData || !orderData.order_id) return;

    showPayWidget(orderData.order_id, amount, description);
}


function showPayWidget(orderId, amount, description) {
    const container = document.getElementById('orders-list');
    container.innerHTML = `
        <div class="card">
            <p><b>Заказ:</b> ${orderId}</p>
            <p><b>Сумма:</b> ${amount} ₽</p>
            <p><b>Описание:</b> ${description}</p>
            <p style="color:#cd7f32;font-size:0.85rem;">Вы будете перенаправлены на платёжную систему Альфа-Банка. Средства будут заморожены до подтверждения выполнения заказа.</p>
            <button class="btn btn-primary" onclick="processAlfaPayment('${orderId}', ${amount}, '${description}')">💳 Перейти к оплате</button>
            <button class="btn btn-link" onclick="goBack()">← Отмена</button>
        </div>
    `;
    goTo('screen-orders');
}

async function processAlfaPayment(orderId, amount, description) {
    showToast('Создаём платёж...', 'info');

    const result = await api('POST', `/orders/${orderId}/pay-alfa`);

    if (result && result.success && result.formUrl) {
        localStorage.setItem('pendingOrderId', orderId);
        window.location.href = result.formUrl;
    } else {
        showToast('Ошибка создания платежа: ' + (result?.message || 'неизвестно'), 'error');
    }
}

async function confirmTestPayment(orderId, amount, description) {
    const result = await api('POST', `/orders/${orderId}/pay-alfa`);
    if (result && result.success) {
        showToast(`Предоплата внесена! ID: ${orderId}`, 'success');
        sendNotification('Новый заказ', `Создан заказ на ${amount} ₽: ${description}`, orderId);
        setTimeout(() => goBack(), 500);
    } else {
        showToast('Ошибка', 'error');
    }
}

async function showMyOrders(filter = 'all') {

    currentView = 'my';
    const data = await api('GET', '/orders', null, { limit: 200, filter });
    const allOrders = data?.orders || [];
    let myOrders;
    if (currentUser.role === 'admin') {
        myOrders = allOrders; // Админ видит все заказы
    } else if (currentUser.role === 'customer') {
        myOrders = allOrders.filter(o => o.customer_id === currentUser.user_id);
    } else {
        myOrders = allOrders.filter(o => o.executor_id === currentUser.user_id);
    }

    const container = document.getElementById('orders-list');
    if (!myOrders.length) {
        container.innerHTML = '<p class="empty">У вас пока нет заказов</p>';
    } else {
        const statusMap = {
            'created': '🆕 Создан', 'hold': '💳 Предоплата', 'in_progress': '🔧 В работе',
            'ready': '👀 Готово', 'back_to_work': '🔁 Доработка',
            'completed': '✅ Завершён', 'cancelled': '❌ Отменён'
        };
        container.innerHTML = myOrders.map(order => {
            const status = statusMap[order.status] || order.status;
            let actions = '';
            if (order.status === 'in_progress' && currentUser.role === 'executor') {
                actions = `<button class="btn btn-secondary btn-sm" onclick="markReady('${order.order_id}')">✅ Я выполнил</button>`;
            }
            if (order.status === 'ready' && currentUser.role === 'customer') {
                actions = `<button class="btn btn-primary btn-sm" onclick="markComplete('${order.order_id}')">💰 Подтвердить</button>
                           <button class="btn btn-link btn-sm" style="color:#cd7f32;" onclick="reworkOrder('${order.order_id}')">🔁 На доработку</button>`;
            }
            if (order.status === 'back_to_work' && currentUser.role === 'executor') {
                actions = `<button class="btn btn-secondary btn-sm" onclick="markReady('${order.order_id}')">✅ Я исправил</button>`;
            }
            if (order.status === 'completed' && currentUser.role === 'customer' && !order.has_review) {
                actions = `<button class="btn btn-outline btn-sm" onclick="showReview('${order.order_id}')">⭐ Оценить</button>`;
            }
            if (order.status !== 'created') {
                actions += `<button class="btn btn-outline btn-sm" onclick="openChat('${order.order_id}')">💬 Чат</button>`;
            }
            if ((order.status === 'hold' || order.status === 'in_progress' || order.status === 'ready') && currentUser.role === 'customer') {
                actions += `<button class="btn btn-link btn-sm" style="color:#8b0000;" onclick="cancelOrder('${order.order_id}')">❌ Отменить</button>`;
            }
            if (order.status === 'completed' && currentUser.role === 'admin') {
                actions += `<button class="btn btn-link btn-sm" style="color:#8b0000;" onclick="refundOrder('${order.order_id}')">↩ Возврат</button>`;
            }
            return `<div class="card">
                <div class="card-header">${order.order_id} <span class="status">${status}</span></div>
                <div class="card-body"><p>${order.description}</p><p class="amount">${order.amount} ₽</p></div>
                ${actions ? `<div class="card-actions">${actions}</div>` : ''}
            </div>`;
        }).join('');
    }
    goTo('screen-orders');
}



function showCreateOrder() {
    goTo('screen-create-order');
}

// ═══════════════════════════════
// ДОСТУПНЫЕ ЗАКАЗЫ
// ═══════════════════════════════

async function showAvailableOrders(filter = 'all') {

    currentView = 'available';
    const data = await api('GET', '/orders', null, { limit: 100, filter });
    const orders = (data?.orders || []).filter(o => o.status === 'hold');
    const container = document.getElementById('orders-list');
    if (!orders.length) {
        container.innerHTML = '<p class="empty">Нет доступных заказов</p>';
    } else {
        container.innerHTML = orders.map(order => `
            <div class="card">
                <div class="card-header">${order.order_id}</div>
                <div class="card-body">
                    <p>${order.description}</p>
                    <p class="amount">${order.amount} ₽ (вам: ${order.amount - order.commission} ₽)</p>
                </div>
                <button class="btn btn-secondary btn-sm" onclick="acceptOrder('${order.order_id}')">✋ Взять</button>
            </div>
        `).join('');
    }
    goTo('screen-orders');
}

async function acceptOrder(orderId) {
    // Если у заказа есть кодовое слово — запрашиваем
    const order = await api('GET', `/orders/${orderId}`);
    if (order && order.secret_code) {
        const code = prompt('Введите кодовое слово для этого заказа:');
        if (code !== order.secret_code) {
            showToast('Неверное кодовое слово', 'error');
            return;
        }
    }

    const data = await api('POST', `/orders/${orderId}/accept`, null, {
        executor_id: currentUser.user_id
    });

    if (data && data.status === 'in_progress') {
        showToast('Заказ взят!', 'success');
        showAvailableOrders();
    } else {
        showToast('Не удалось взять заказ', 'error');
    }
}


// ═══════════════════════════════
// МОИ ЗАКАЗЫ
// ═══════════════════════════════






// ═══════════════════════════════
// ДЕЙСТВИЯ
// ═══════════════════════════════

async function markReady(orderId) {
    const data = await api('POST', `/orders/${orderId}/ready`);
    if (data) {
        showToast('Заказчик уведомлён! Ожидайте подтверждения.', 'success');
        sendNotification('Заказ готов', `Заказ ${orderId} выполнен`, orderId);
        showMyOrders();
    }
}

async function markComplete(orderId) {
    if (!confirm(
        '✅ Подтверждаю, что проверил(а) результат работы.\n' +
        'Работа соответствует моим требованиям.\n' +
        'Деньги будут перечислены исполнителю.\n' +
        'Работа будет считаться завершённой.\n\n' +
        'Согласно ст. 720 ГК РФ, заказчик обязан осмотреть и принять выполненную работу.'
    )) return;

    const data = await api('POST', `/orders/${orderId}/complete`);
    if (data && data.success) {
        showToast('Заказ завершён!', 'success');
        sendNotification('Заказ подтверждён', `Заказ ${orderId} завершён`, 'completed-' + orderId);
        showMyOrders();
    } else {
        showToast('Ошибка: ' + (data?.message || 'неизвестно'), 'error');
    }
}

async function cancelOrder(orderId) {
    if (!confirm('Отменить заказ? Деньги вернутся заказчику.')) return;

    const data = await api('POST', `/orders/${orderId}/cancel`);
    if (data && data.success) {
        showToast('Заказ отменён, деньги возвращены', 'success');
        showMyOrders();
    }
}

async function reworkOrder(orderId) {
    const data = await api('POST', `/orders/${orderId}/rework`);
    if (data && data.status === 'back_to_work') {
        showToast('Заказ возвращён на доработку', 'info');
        showMyOrders();
    }
}

function refreshOrders(filter = 'all') {
    if (currentView === 'available') {
        showAvailableOrders(filter);
    } else {
        showMyOrders(filter);
    }
}



async function refundOrder(orderId) {
    if (!confirm('Вернуть деньги за заказ ' + orderId + '?')) return;
    const result = await api('POST', `/orders/${orderId}/refund`);
    if (result && result.success) {
        showToast('Деньги возвращены', 'success');
        showMyOrders();
    } else {
        showToast('Ошибка возврата', 'error');
    }
}

let allOrdersCache = []; // Кэш всех заказов

function searchOrders() {
    const query = document.getElementById('search-orders').value.trim().toLowerCase();
    const container = document.getElementById('orders-list');

    if (!query) {
        // Если поиск пустой — показываем все заказы
        renderOrders(allOrdersCache);
        return;
    }

    // Фильтруем по номеру заказа или описанию
    const filtered = allOrdersCache.filter(o =>
        o.order_id.toLowerCase().includes(query) ||
        o.description.toLowerCase().includes(query)
    );

    renderOrders(filtered);
}

// ═══════════════════════════════
// ОТЗЫВЫ
// ═══════════════════════════════

function showReview(orderId) {
    currentOrderForReview = orderId;
    currentRating = 0;
    document.querySelectorAll('#stars-container span').forEach(s => { s.textContent = '☆'; s.style.color = '#3d1a1a'; });
    document.getElementById('review-comment').value = '';
    goTo('screen-review');
}

function setRating(rating) {
    currentRating = rating;
    document.querySelectorAll('#stars-container span').forEach((s, i) => {
        s.textContent = i < rating ? '★' : '☆';
        s.style.color = i < rating ? '#cd7f32' : '#3d1a1a';
    });
}

async function submitReview() {
    if (!currentRating) { showToast('Поставьте оценку', 'error'); return; }
    const comment = document.getElementById('review-comment').value.trim();
    const data = await api('POST', '/reviews/create', {
        order_id: currentOrderForReview,
        customer_id: currentUser.user_id,
        rating: currentRating,
        comment
    });
    if (data && data.review_id) { showToast('Спасибо за оценку!', 'success'); goBack(); }
}


// ═══════════════════════════════
// СТАТИСТИКА
// ═══════════════════════════════

async function showStats() {
    const data = await api('GET', `/users/${currentUser.user_id}/stats`);
    if (!data) return;
    document.getElementById('stats-content').innerHTML = `
        <div class="card">
            <p><b>Имя:</b> ${data.full_name}</p>
            <p><b>Рейтинг:</b> ${'★'.repeat(Math.round(data.rating))} (${data.rating})</p>
            <p><b>Всего отзывов:</b> ${data.total_reviews}</p>
            <p><b>Выполнено заказов:</b> ${data.completed_orders}</p>
            <p><b>Заработано:</b> ${data.total_earned} ₽</p>
        </div>`;
    goTo('screen-stats');
}


// ═══════════════════════════════
// ВЫХОД
// ═══════════════════════════════

function logout() {
    if (currentUser) localStorage.removeItem(`${currentUser.role}_userId`);
    currentUser = null;
    goTo('screen-role');
    showToast('Вы вышли', 'info');
}

// ═══════════════════════════════
// ЧАТ
// ═══════════════════════════════

function refreshOrders(filter = 'all') {
    if (currentView === 'available') {
        showAvailableOrders(filter);
    } else {
        showMyOrders(filter);
    }
}

let chatTimer = null;

async function openChat(orderId) {
    currentChatOrderId = orderId;
    document.getElementById('chat-order-id').textContent = orderId;
    document.getElementById('chat-input').value = '';
    goTo('screen-chat');
    await loadChatMessages();

    // Автообновление каждые 3 секунды
    if (chatTimer) clearInterval(chatTimer);
    chatTimer = setInterval(loadChatMessages, 3000);
}



async function loadChatMessages() {
    const data = await api('GET', `/chat/${ currentChatOrderId }`);
    const container = document.getElementById('chat-messages');
    const messages = data?.messages || [];

    if (!messages.length) {
        container.innerHTML = '<p class="empty">Нет сообщений. Напишите первым!</p>';
        return;
    }

    container.innerHTML = messages.map(m => {
        const isMe = m.sender_id === currentUser.user_id;
        return `
            <div style="margin-bottom:8px;text-align:${isMe ? 'right' : 'left'};">
                <div style="display:inline-block;max-width:80%;padding:10px 14px;
                    background:${isMe ? 'rgba(205,127,50,0.2)' : 'rgba(255,255,255,0.05)'};
                    border-left:3px solid ${isMe ? '#cd7f32' : '#555'};">
                    <div style="font-size:0.7rem;color:#8b6b4b;">${m.sender_name}</div>
                    <div style="color:#f0e6d2;">${m.text}</div>
                    <div style="font-size:0.6rem;color:#555;text-align:right;">${new Date(m.created_at).toLocaleTimeString()}</div>
                </div>
            </div>
        `;
    }).join('');

    // Прокрутка вниз
    container.scrollTop = container.scrollHeight;
}

async function sendChatMessage() {
    if (!currentUser || !currentUser.user_id) {
        showToast('Вы не авторизованы. Выйдите и зайдите снова.', 'error');
        return;
    }
    const input = document.getElementById('chat-input');
    const text = input.value.trim();
    if (!text) return;

    await api('POST', '/chat/send', {
        order_id: currentChatOrderId,
        sender_id: currentUser.user_id,
        sender_name: currentUser.full_name || 'Пользователь',
        text
    });

    input.value = '';
    await loadChatMessages();
}

// ═══════════════════════════════
// PUSH-УВЕДОМЛЕНИЯ
// ═══════════════════════════════

async function toggleNotifications() {
    if (!('Notification' in window)) {
        showToast('Ваш браузер не поддерживает уведомления', 'error');
        return;
    }

    const btn = document.getElementById('btn-notif-toggle');

    // Если уже включены — выключаем
    if (Notification.permission === 'granted' && notificationsEnabled) {
        notificationsEnabled = false;
        if (btn) btn.textContent = '🔕';
        showToast('Уведомления отключены', 'info');
        return;
    }

    // Если запрещены в настройках браузера
    if (Notification.permission === 'denied') {
        showToast('Разрешите уведомления в настройках браузера', 'error');
        return;
    }

    // Запрашиваем разрешение
    const permission = await Notification.requestPermission();

    if (permission === 'granted') {
        notificationsEnabled = true;
        if (btn) btn.textContent = '🔔';
        showToast('Уведомления включены!', 'success');

        new Notification('Платформа', {
            body: 'Вы будете получать уведомления о новых заказах',
            icon: '/static/icon-192.png'
        });
    } else {
        notificationsEnabled = false;
        if (btn) btn.textContent = '🔕';
        showToast('Вы отказались от уведомлений', 'error');
    }
}


function sendNotification(title, body, orderId) {
    addNotification(title, body, orderId);

    if (!notificationsEnabled || Notification.permission !== 'granted') return;

    new Notification(title, {
        body: body,
        icon: '/static/icon-192.png',
        tag: 'notif-' + orderId,
        requireInteraction: true
    });
}

function addNotification(title, body, orderId) {
    const notif = {
        id: Date.now(),
        title,
        body,
        orderId,    // ← чистый orderId
        time: new Date().toLocaleTimeString(),
        read: false
    };
    notificationsList.unshift(notif);
    if (notificationsList.length > 50) notificationsList.pop();

    try {
        localStorage.setItem('notifications', JSON.stringify(notificationsList.slice(0, 50)));
    } catch(e) {}
}

function showNotifications() {
    const container = document.getElementById('notifications-list');

    if (!notificationsList.length) {
        container.innerHTML = '<p class="empty">Нет уведомлений</p>';
    } else {
        container.innerHTML = notificationsList.map(n => `
            <div class="card" style="${n.read ? 'opacity:0.6;' : ''}">
                <div class="card-header">
                    ${n.title}
                    <span class="status">${n.time}</span>
                </div>
                <div class="card-body">
                    <p>${n.body}</p>
                </div>
                ${n.orderId ? `<button class="btn btn-outline btn-sm" onclick="openChat('${n.orderId}')">💬 К заказу</button>` : ''}
            </div>
        `).join('');

        // Пометить как прочитанные
        notificationsList.forEach(n => n.read = true);
        try {
            localStorage.setItem('notifications', JSON.stringify(notificationsList.slice(0, 50)));
        } catch(e) {}
    }

    goTo('screen-notifications');
}

function clearNotifications() {
    if (!confirm('Удалить все уведомления?')) return;
    notificationsList = [];
    localStorage.removeItem('notifications');
    showNotifications();
    showToast('Уведомления очищены', 'info');
}









// ═══════════════════════════════
// ЗАПУСК
// ═══════════════════════════════

(function init() {
    // Скрываем все экраны
    document.querySelectorAll('.screen').forEach(s => { s.style.display = 'none'; s.classList.remove('active'); });

    const pendingOrderId = localStorage.getItem('pendingOrderId');
    if (pendingOrderId) {
        showToast('Проверяем статус платежа...', 'info');
        localStorage.removeItem('pendingOrderId');
        setTimeout(async () => {
            const order = await api('GET', `/orders/${pendingOrderId}`);
            if (order && order.status === 'hold') {
                showToast('Оплата прошла!', 'success');
            }
        }, 2000);
    }

    // Загружаем сохранённые уведомления
    try {
        const saved = localStorage.getItem('notifications');
        if (saved) notificationsList = JSON.parse(saved);
    } catch(e) {}

    // Показываем главный экран
    const roleScreen = document.getElementById('screen-role');
    if (roleScreen) { roleScreen.style.display = 'flex'; roleScreen.classList.add('active'); }

    // Проверяем, вернулся ли пользователь после оплаты
    const urlParams = new URLSearchParams(window.location.search);
    const paidOrderId = urlParams.get('paid');
    if (paidOrderId) {
        api('POST', `/orders/${paidOrderId}/confirm-payment`, null, {
            transaction_id: 'cp_' + Date.now()
        }).then(result => {
            if (result && result.success) {
                showToast('Оплата прошла! Заказ ' + paidOrderId, 'success');
            }
        });
        window.history.replaceState({}, document.title, '/app');
    }
})();
