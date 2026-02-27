/**
 * Chat Poll Module
 * Управление голосованиями в чате
 */

export class ChatPoll {
	constructor(options = {}) {
		this.chatId = options.chatId;
		this.createUrl = options.createUrl || '/api/v1/communications/polls/';
		this.voteUrl = options.voteUrl || '/api/v1/communications/polls/{poll_id}/vote/';
		this.closeUrl = options.closeUrl || '/api/v1/communications/polls/{poll_id}/close/';
		this.resultsUrl = options.resultsUrl || '/api/v1/communications/polls/{poll_id}/results/';
		
		this.modal = document.getElementById('pollModal');
		this.modalInstance = null;
		
		if (this.modal && typeof bootstrap !== 'undefined') {
			this.modalInstance = new bootstrap.Modal(this.modal);
		}
		
		this.bindEvents();
		this.initializeExistingPolls();
	}
	
	initializeExistingPolls() {
		const pollWidgets = document.querySelectorAll('.poll-widget[data-poll-id]');
		console.log('[ChatPoll] initializeExistingPolls: found %d widgets', pollWidgets.length);
		
		if (!pollWidgets.length) return;

		pollWidgets.forEach((widget) => {
			const pollId = widget.dataset.pollId;
			console.log('[ChatPoll] Initializing poll widget, poll_id=%s', pollId);
			if (!pollId) {
				return;
			}
			this.refreshPoll(pollId, widget);
		});
	}

	async refreshPoll(pollId, pollWidget = null) {
		console.log('[ChatPoll] refreshPoll called, poll_id=%s', pollId);
		const widget = pollWidget || document.querySelector(`[data-poll-id="${pollId}"]`);
		if (!widget) {
			console.warn('[ChatPoll] Widget not found for poll_id=%s', pollId);
			return;
		}

		// Загружаем актуальные данные с сервера
		const results = await this.fetchPollResults(pollId);
		console.log('[ChatPoll] refreshPoll: fetched results for poll_id=%s:', pollId, results);
		if (!results) return;

		// Обновляем UI опроса (проценты, счётчики, кнопки)
		this.updatePollWidget(widget, results);
	}

	async fetchPollResults(pollId) {
		const url = this.resultsUrl.replace('{poll_id}', pollId);
		try {
			const response = await fetch(url);
			if (!response.ok) {
				throw new Error(`Failed to fetch poll results (${response.status})`);
			}
			const data = await response.json();
			console.log('[ChatPoll] Fetched poll results for poll_id=%s:', pollId, data);
			console.log('[ChatPoll] user_voted_option_ids:', data.user_voted_option_ids);
			return data;
		} catch (error) {
			console.error('Error fetching poll results:', error);
			return null;
		}
	}
	bindEvents() {
		// Кнопка "Создать голосование"
		const createBtn = document.getElementById('createPoll');
		if (createBtn) {
			createBtn.addEventListener('click', (e) => {
				e.preventDefault();
				this.openModal();
			});
		}
		
		// Добавить вариант ответа
		const addOptionBtn = document.getElementById('addPollOption');
		if (addOptionBtn) {
			addOptionBtn.addEventListener('click', () => this.addOption());
		}
		
		// Викторина - показать выбор правильного ответа
		const quizCheckbox = document.getElementById('pollQuiz');
		if (quizCheckbox) {
			quizCheckbox.addEventListener('change', (e) => {
				const correctAnswerDiv = document.getElementById('quizCorrectAnswer');
				if (correctAnswerDiv) {
					correctAnswerDiv.style.display = e.target.checked ? 'block' : 'none';
				}
			});
		}
		
		// Отправка голосования
		const submitBtn = document.getElementById('submitPoll');
		if (submitBtn) {
			submitBtn.addEventListener('click', () => this.submitPoll());
		}
		
		// Обновление списка правильных ответов при изменении вариантов
		const pollOptionsContainer = document.getElementById('pollOptions');
		if (pollOptionsContainer) {
			pollOptionsContainer.addEventListener('input', () => {
				this.updateCorrectAnswerOptions();
			});
		}
		
		// Делегирование событий для кнопок голосования (динамически добавленные)
		document.addEventListener('click', (e) => {
			const pollOptionBtn = e.target.closest('.btn-poll-option');
			if (pollOptionBtn) {
				e.preventDefault();
				const optionId = parseInt(pollOptionBtn.dataset.optionId, 10);
				const pollWidget = pollOptionBtn.closest('.poll-widget');
				if (pollWidget) {
					const pollId = parseInt(pollWidget.dataset.pollId, 10);
					this.handlePollVote(pollId, optionId, pollWidget);
				}
			}
			
			// Показать/скрыть список проголосовавших
			const votersToggle = e.target.closest('.poll-voters-toggle');
			if (votersToggle) {
				e.preventDefault();
				const votersList = votersToggle.nextElementSibling;
				if (votersList && votersList.classList.contains('poll-voters-list')) {
					const isVisible = votersList.style.display !== 'none';
					votersList.style.display = isVisible ? 'none' : 'block';
					const icon = votersToggle.querySelector('i');
					if (icon) {
						icon.className = isVisible ? 'bi-chevron-down' : 'bi-chevron-up';
					}
				}
			}
		});
	}
	
	async handlePollVote(pollId, optionId, pollWidget) {
		// Проверяем не закрыто ли голосование
		const footerText = pollWidget.querySelector('.poll-footer .text-muted')?.textContent || '';
		if (footerText.includes('Закрыто')) {
			alert('Голосование закрыто');
			return;
		}
		
		console.log('[ChatPoll] Voting: poll_id=%s, option_id=%s', pollId, optionId);
		
		// Блокируем кнопки на время голосования
		const optionButtons = pollWidget.querySelectorAll('.btn-poll-option');
		optionButtons.forEach(btn => {
			btn.disabled = true;
			btn.classList.add('disabled');
		});
		
		// Показываем индикатор загрузки
		const clickedButton = pollWidget.querySelector(`[data-option-id="${optionId}"]`);
		if (clickedButton) {
			const originalText = clickedButton.textContent;
			clickedButton.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Отправка...';
			clickedButton.dataset.originalText = originalText;
		}
		
		// Отправляем голос (НЕ обновляем UI сразу!)
		const results = await this.vote(pollId, [optionId]);
		
		if (!results) {
			// Если ошибка - разблокируем кнопки
			console.error('[ChatPoll] Vote failed, restoring buttons');
			optionButtons.forEach(btn => {
				btn.disabled = false;
				btn.classList.remove('disabled');
			});
			
			if (clickedButton && clickedButton.dataset.originalText) {
				clickedButton.textContent = clickedButton.dataset.originalText;
			}
		} else {
			console.log('[ChatPoll] Vote sent successfully, waiting for WebSocket update...');
		}
		
		// UI обновится автоматически через WebSocket событие 'chat:poll-update'
		// которое обработает chat-detail-enhanced.js → chatPoll.updatePollWidget()
	}
	
	updatePollWidget(pollWidget, results) {
		if (!pollWidget) return;
		
		console.log('[ChatPoll] Updating poll widget, poll_id=%s', results.id);
		console.log('[ChatPoll] Results:', results);
		console.log('[ChatPoll] Results.options:', results.options);
		
		this.updatePollFooter(pollWidget, results);
		
		const userVotes = Array.isArray(results.user_voted_option_ids)
			? results.user_voted_option_ids
			: [];
		
		// Явное преобразование is_closed в boolean (может прийти как строка "true"/"false")
		const isClosed = results.is_closed === true || results.is_closed === 'true' || results.is_closed === 'True';
		const shouldShowResults = userVotes.length > 0 || isClosed;
		
		console.log('[ChatPoll] User votes:', userVotes, 'shouldShowResults:', shouldShowResults);
		console.log('[ChatPoll] is_closed:', results.is_closed, '(type: %s)', typeof results.is_closed, 'isClosed:', isClosed, 'userVotes.length:', userVotes.length);
		
		const optionsContainer = pollWidget.querySelector('.poll-options');
		if (!optionsContainer) return;
		
		optionsContainer.innerHTML = '';
		
		if (!shouldShowResults) {
			// Показываем кнопки для голосования
			results.options.forEach(option => {
				const optionDiv = document.createElement('div');
				optionDiv.className = 'poll-option mb-2';
				optionDiv.dataset.optionId = option.id;
				
				optionDiv.innerHTML = `
					<button type="button" class="btn btn-outline-secondary btn-poll-option w-100 text-start" 
							data-option-id="${option.id}">
						${this.constructor.escapeHtml(option.text)}
					</button>
				`;
				
				optionsContainer.appendChild(optionDiv);
			});
			return;
		}
		
		// Показываем результаты с прогресс-барами
		results.options.forEach(option => {
			const isVoted = userVotes.includes(option.id);
			const percentage = option.percentage || 0;
			const voteCount = option.vote_count || 0;
			const voters = option.voters || [];
			
			console.log('[ChatPoll] Rendering option:', {
				id: option.id,
				text: option.text,
				percentage,
				voteCount,
				isVoted,
				votersCount: voters.length
			});
			
			const optionDiv = document.createElement('div');
			optionDiv.className = `poll-option mb-2 ${isVoted ? 'voted' : ''}`;
			optionDiv.dataset.optionId = option.id;
			
			// Формируем HTML списка проголосовавших
			let votersHtml = '';
			if (!results.is_anonymous && voters.length > 0) {
				votersHtml = `
					<div class="poll-voters mt-2">
						<a href="#" class="poll-voters-toggle small text-primary text-decoration-none">
							<i class="bi-chevron-down me-1"></i>
							${voteCount} ${this.constructor.pluralize(voteCount, 'проголосовал', 'проголосовало', 'проголосовало')}
						</a>
						<div class="poll-voters-list small text-muted mt-1" style="display: none; padding-left: 1.25rem;">
							${voters.map(voter => `
								<div class="voter-item">
									<i class="bi-person-fill me-1"></i>
									${this.constructor.escapeHtml(voter.voter__first_name || '')} 
									${this.constructor.escapeHtml(voter.voter__last_name || '')}
								</div>
							`).join('')}
						</div>
					</div>
				`;
			} else if (!results.is_anonymous && voteCount > 0) {
				votersHtml = `<div class="small text-muted mt-1">${voteCount} ${this.constructor.pluralize(voteCount, 'голос', 'голоса', 'голосов')}</div>`;
			}
			
			optionDiv.innerHTML = `
				<div class="poll-option-result">
					<div class="d-flex justify-content-between align-items-center mb-1">
						<span>
							${isVoted ? '<i class="bi-check-circle-fill text-success me-1"></i>' : ''}
							${this.constructor.escapeHtml(option.text)}
						</span>
						<span class="text-muted small">${percentage}%</span>
					</div>
					<div class="progress" style="height: 6px;">
						<div class="progress-bar" role="progressbar" 
							 style="width: ${percentage}%" 
							 aria-valuenow="${percentage}" 
							 aria-valuemin="0" 
							 aria-valuemax="100"></div>
					</div>
					${votersHtml}
				</div>
			`;
			
			optionsContainer.appendChild(optionDiv);
		});
	}

	updatePollFooter(pollWidget, results) {
		const footer = pollWidget.querySelector('.poll-footer .text-muted');
		if (!footer) return;
		const totalVoters = results.total_voters || 0;
		footer.innerHTML = `
			${totalVoters} ${this.constructor.pluralize(totalVoters, 'проголосовал', 'проголосовало', 'проголосовало')}
			${results.is_anonymous ? ' • Анонимное' : ''}
			${results.is_multiple_choice ? ' • Множественный выбор' : ''}
			${results.is_closed ? ' • Закрыто' : ''}
		`;
	}
	
	openModal() {
		if (!this.modalInstance) {
			console.error('Poll modal not initialized');
			return;
		}
		
		// Сброс формы
		this.resetForm();
		this.modalInstance.show();
	}
	
	resetForm() {
		// Очистить вопрос
		const questionInput = document.getElementById('pollQuestion');
		if (questionInput) {
			questionInput.value = '';
		}
		
		// Сбросить варианты ответа
		const optionsContainer = document.getElementById('pollOptions');
		if (optionsContainer) {
			optionsContainer.innerHTML = `
				<div class="input-group mb-2">
					<span class="input-group-text">1</span>
					<input type="text" class="form-control poll-option" 
						   placeholder="Вариант ответа" maxlength="200">
					<button type="button" class="btn btn-outline-danger btn-sm remove-option" style="display:none;">
						<i class="bi-x-circle"></i>
					</button>
				</div>
				<div class="input-group mb-2">
					<span class="input-group-text">2</span>
					<input type="text" class="form-control poll-option" 
						   placeholder="Вариант ответа" maxlength="200">
					<button type="button" class="btn btn-outline-danger btn-sm remove-option" style="display:none;">
						<i class="bi-x-circle"></i>
					</button>
				</div>
			`;
		}
		
		// Сбросить чекбоксы
		['pollAnonymous', 'pollMultiple', 'pollQuiz'].forEach(id => {
			const checkbox = document.getElementById(id);
			if (checkbox) {
				checkbox.checked = false;
			}
		});
		
		// Скрыть выбор правильного ответа
		const correctAnswerDiv = document.getElementById('quizCorrectAnswer');
		if (correctAnswerDiv) {
			correctAnswerDiv.style.display = 'none';
		}
		
		// Очистить время закрытия
		const closesInput = document.getElementById('pollCloses');
		if (closesInput) {
			closesInput.value = '';
		}
	}
	
	addOption() {
		const optionsContainer = document.getElementById('pollOptions');
		if (!optionsContainer) return;
		
		const currentCount = optionsContainer.querySelectorAll('input.poll-option').length;
		
		if (currentCount >= 10) {
			alert('Максимум 10 вариантов ответа');
			return;
		}
		
		const newOption = document.createElement('div');
		newOption.className = 'input-group mb-2';
		newOption.innerHTML = `
			<span class="input-group-text">${currentCount + 1}</span>
			<input type="text" class="form-control poll-option" 
				   placeholder="Вариант ответа" maxlength="200">
			<button type="button" class="btn btn-outline-danger btn-sm remove-option">
				<i class="bi-x-circle"></i>
			</button>
		`;
		
		optionsContainer.appendChild(newOption);
		
		// Показать кнопки удаления если больше 2 вариантов
		if (currentCount + 1 > 2) {
			optionsContainer.querySelectorAll('.remove-option').forEach(btn => {
				btn.style.display = 'inline-block';
				btn.onclick = (e) => this.removeOption(e);
			});
		}
		
		this.updateCorrectAnswerOptions();
	}
	
	removeOption(event) {
		const optionsContainer = document.getElementById('pollOptions');
		if (!optionsContainer) return;
		
		const optionGroup = event.target.closest('.input-group');
		if (!optionGroup) return;
		
		optionGroup.remove();
		
		// Обновить нумерацию
		const options = optionsContainer.querySelectorAll('.input-group');
		options.forEach((group, index) => {
			const numberSpan = group.querySelector('.input-group-text');
			if (numberSpan) {
				numberSpan.textContent = index + 1;
			}
		});
		
		// Скрыть кнопки удаления если осталось 2 варианта
		if (options.length <= 2) {
			optionsContainer.querySelectorAll('.remove-option').forEach(btn => {
				btn.style.display = 'none';
			});
		}
		
		this.updateCorrectAnswerOptions();
	}
	
	updateCorrectAnswerOptions() {
		const correctSelect = document.getElementById('pollCorrectOption');
		if (!correctSelect) return;
		
		// Ищем только input элементы внутри формы создания голосования
		const optionsContainer = document.getElementById('pollOptions');
		if (!optionsContainer) return;
		
		const options = optionsContainer.querySelectorAll('input.poll-option');
		correctSelect.innerHTML = '<option value="">Выберите правильный вариант</option>';
		
		options.forEach((input, index) => {
			const text = input.value?.trim() || '';
			if (text) {
				const option = document.createElement('option');
				option.value = index;
				option.textContent = `${index + 1}. ${text.substring(0, 50)}${text.length > 50 ? '...' : ''}`;
				correctSelect.appendChild(option);
			}
		});
	}
	
	async submitPoll() {
		// Валидация
		const questionInput = document.getElementById('pollQuestion');
		const question = questionInput?.value?.trim() || '';
		
		if (!question) {
			alert('Введите вопрос');
			questionInput?.focus();
			return;
		}
		
		// Собрать варианты ответов - ищем только в форме создания
		const optionsContainer = document.getElementById('pollOptions');
		if (!optionsContainer) {
			console.error('Poll options container not found');
			return;
		}
		
		const optionInputs = optionsContainer.querySelectorAll('input.poll-option');
		const options = Array.from(optionInputs)
			.map(input => input.value?.trim() || '')
			.filter(text => text.length > 0);
		
		if (options.length < 2) {
			alert('Необходимо минимум 2 варианта ответа');
			return;
		}
		
		// Настройки
		const isAnonymous = document.getElementById('pollAnonymous')?.checked || false;
		const isMultiple = document.getElementById('pollMultiple')?.checked || false;
		const isQuiz = document.getElementById('pollQuiz')?.checked || false;
		
		let correctOptionIndex = null;
		if (isQuiz) {
			const correctSelect = document.getElementById('pollCorrectOption');
			correctOptionIndex = correctSelect?.value ? parseInt(correctSelect.value, 10) : null;
			
			if (correctOptionIndex === null || isNaN(correctOptionIndex)) {
				alert('Для викторины выберите правильный ответ');
				return;
			}
		}
		
		const closesInMinutes = parseInt(document.getElementById('pollCloses')?.value, 10) || null;
		
		// Отправка
		const submitBtn = document.getElementById('submitPoll');
		if (submitBtn) {
			submitBtn.disabled = true;
			submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Создание...';
		}
		
		try {
			const response = await fetch(this.createUrl, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					'X-CSRFToken': this.getCsrfToken()
				},
				body: JSON.stringify({
					chat_id: this.chatId,
					question,
					options_data: options,  // Исправлено: options_data вместо options
					is_anonymous: isAnonymous,
					is_multiple_choice: isMultiple,
					is_quiz: isQuiz,
					correct_option_index: correctOptionIndex,
					closes_in_minutes: closesInMinutes
				})
			});
			
			const data = await response.json();
			
			if (response.ok) {
				// Закрыть модалку
				if (this.modalInstance) {
					this.modalInstance.hide();
				}
				
				// Сообщение о успехе
				console.log('Poll created:', data);
				
				// Голосование появится через WebSocket
			} else {
				alert(data.error || 'Ошибка создания голосования');
			}
		} catch (error) {
			console.error('Error creating poll:', error);
			alert('Ошибка при создании голосования');
		} finally {
			if (submitBtn) {
				submitBtn.disabled = false;
				submitBtn.innerHTML = '<i class="bi-check-circle me-1"></i>Создать';
			}
		}
	}
	
	async vote(pollId, optionIds) {
		if (!Array.isArray(optionIds)) {
			optionIds = [optionIds];
		}
		
		const url = this.voteUrl.replace('{poll_id}', pollId);
		
		try {
			const response = await fetch(url, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					'X-CSRFToken': this.getCsrfToken()
				},
				body: JSON.stringify({
					poll_id: pollId,
					option_ids: optionIds
				})
			});
			
			const data = await response.json();
			
			if (response.ok) {
				return data.results;
			} else {
				alert(data.error || 'Ошибка голосования');
				return null;
			}
		} catch (error) {
			console.error('Error voting:', error);
			alert('Ошибка при голосовании');
			return null;
		}
	}
	
	async closePoll(pollId) {
		const url = this.closeUrl.replace('{poll_id}', pollId);
		
		try {
			const response = await fetch(url, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					'X-CSRFToken': this.getCsrfToken()
				},
				body: JSON.stringify({ poll_id: pollId })
			});
			
			const data = await response.json();
			
			if (response.ok) {
				console.log('Poll closed');
				return true;
			} else {
				alert(data.error || 'Ошибка закрытия голосования');
				return false;
			}
		} catch (error) {
			console.error('Error closing poll:', error);
			alert('Ошибка при закрытии голосования');
			return false;
		}
	}
	
	getCsrfToken() {
		// Сначала пробуем получить из input
		const tokenEl = document.querySelector('[name=csrfmiddlewaretoken]');
		if (tokenEl && tokenEl.value) {
			return tokenEl.value;
		}
		
		// Если нет, получаем из cookie
		const match = document.cookie.match(/csrftoken=([^;]+)/);
		return match ? match[1] : '';
	}
	
	/**
	 * Рендер HTML для голосования
	 */
	static renderPoll(poll, userVotedOptionIds = []) {
		const totalVotes = poll.total_voters || 0;
		const isClosed = poll.is_closed;
		const hasVoted = userVotedOptionIds.length > 0;
		
		let html = `
			<div class="poll-widget" data-poll-id="${poll.id}">
				<div class="poll-question mb-3">
					<strong>${this.escapeHtml(poll.question)}</strong>
				</div>
				<div class="poll-options">
		`;
		
		poll.options.forEach(option => {
			const isVoted = userVotedOptionIds.includes(option.id);
			const percentage = option.percentage || 0;
			const voteCount = option.vote_count || 0;
			const voters = option.voters || [];
			
			// Показываем результаты если голосование закрыто или пользователь проголосовал
			const showResults = isClosed || hasVoted;
			
			// Формируем HTML списка проголосовавших
			let votersHtml = '';
			if (!poll.is_anonymous && voters.length > 0) {
				votersHtml = `
					<div class="poll-voters mt-2">
						<a href="#" class="poll-voters-toggle small text-primary text-decoration-none">
							<i class="bi-chevron-down me-1"></i>
							${voteCount} ${this.pluralize(voteCount, 'проголосовал', 'проголосовало', 'проголосовало')}
						</a>
						<div class="poll-voters-list small text-muted mt-1" style="display: none; padding-left: 1.25rem;">
							${voters.map(voter => `
								<div class="voter-item">
									<i class="bi-person-fill me-1"></i>
									${this.escapeHtml(voter.voter__first_name || '')} 
									${this.escapeHtml(voter.voter__last_name || '')}
								</div>
							`).join('')}
						</div>
					</div>
				`;
			} else if (!poll.is_anonymous && voteCount > 0) {
				votersHtml = `<div class="small text-muted mt-1">${voteCount} ${this.pluralize(voteCount, 'голос', 'голоса', 'голосов')}</div>`;
			}
			
			html += `
				<div class="poll-option mb-2 ${isVoted ? 'voted' : ''}" data-option-id="${option.id}">
					${showResults ? `
						<div class="poll-option-result">
							<div class="d-flex justify-content-between align-items-center mb-1">
								<span>
									${isVoted ? '<i class="bi-check-circle-fill text-success me-1"></i>' : ''}
									${this.escapeHtml(option.text)}
								</span>
								<span class="text-muted small">${percentage}%</span>
							</div>
							<div class="progress" style="height: 6px;">
								<div class="progress-bar" role="progressbar" 
									 style="width: ${percentage}%" 
									 aria-valuenow="${percentage}" 
									 aria-valuemin="0" 
									 aria-valuemax="100"></div>
							</div>
							${votersHtml}
						</div>
					` : `
						<button type="button" class="btn btn-outline-secondary btn-poll-option w-100 text-start" 
								data-option-id="${option.id}">
							${this.escapeHtml(option.text)}
						</button>
					`}
				</div>
			`;
		});
		
		html += `
				</div>
				<div class="poll-footer mt-3 d-flex justify-content-between align-items-center">
					<div class="small text-muted">
						${totalVotes} ${this.pluralize(totalVotes, 'проголосовал', 'проголосовало', 'проголосовало')}
						${poll.is_anonymous ? ' • Анонимное' : ''}
						${poll.is_multiple_choice ? ' • Множественный выбор' : ''}
						${isClosed ? ' • Закрыто' : ''}
					</div>
					${!isClosed && hasVoted ? `
						<button type="button" class="btn btn-sm btn-link text-danger" data-action="retract-vote">
							Отменить голос
						</button>
					` : ''}
				</div>
			</div>
		`;
		
		return html;
	}
	
	static escapeHtml(text) {
		const div = document.createElement('div');
		div.textContent = text;
		return div.innerHTML;
	}
	
	static pluralize(count, one, few, many) {
		const mod10 = count % 10;
		const mod100 = count % 100;
		
		if (mod10 === 1 && mod100 !== 11) {
			return one;
		}
		if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) {
			return few;
		}
		return many;
	}
}

export default ChatPoll;
