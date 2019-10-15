define(['jquery'], function($){
    var CustomWidget = function () {
    	var self = this,
		current_user = AMOCRM.constant('user').id;
		
		var settings = self.params;
		settings.phones = JSON.parse(settings.phones);
		var amoUsers = {};
		for(var user in settings.phones) {
			amoUsers[user] = {}
			params = settings.phones[user].split(',');
			for(var i in params) {
				if (params[i].split('=')[1] !== undefined){
					amoUsers[user][params[i].split('=')[0]] = params[i].split('=')[1];
				}
				else {
					channel = params[i].split('=')[0];
					if(channel.split('/')[1] !== undefined) {
						amoUsers[user].protocol = channel.split('/')[0];
						amoUsers[user].phone = channel.split('/')[1];
					}
					else {
						amoUsers[user].phone = channel;
						amoUsers[user].protocol = 'SIP';
					};
				};
			};
		};
		
		this.callbacks = {
			render: function(){
				return true;
			},
			init: function(){
				console.log(amoUsers);
				var w_code = self.get_settings().widget_code;
				$('head').append('<link type="text/css" rel="stylesheet" href="/upl/'+w_code+'/widget/style.css">');
				
				window.openwindows = [];		
				setInterval(function() {
					$.get(settings.scriptPath + '/api/status')
					.done(function(response) {
						var callback = this.asteriskHandler(response);
						for(var i in callback.number) {
							if (callback.state[i] == 'Ringing' && callback.number[i] !== amoUsers[current_user].phone) {
								$.get('//'+window.location.host+'/private/api/contact_search.php?SEARCH='+callback.number[i], function (contact) {
									if ($(contact).find('contact > id').eq(0).text().length > 0) {
										if ($(contact).find('contact > is_company').eq(0).text().indexOf('1') != -1){
											var n_data = {
															id: callback.number[i],
															title: '<a class="popup-link" href= "//'+window.location.host+'/companies/detail/'+$(contact).find('contact > id').eq(0).text()+'" target="_blank">'+$(contact).find('contact > name').eq(0).text()+'</a>',
															text: '<span>'+callback.number[i]+'</span>'
														};
										}
										else{
											var n_data = {
															id: callback.number[i],
															title: '<a class="popup-link" href= "//'+window.location.host+'/contacts/detail/'+$(contact).find('contact > id').eq(0).text()+'" target="_blank">'+$(contact).find('contact > name').eq(0).text()+'</a>',
															text: '<span>'+callback.number[i]+'</span>'
														};
										};
									}		
									else{
										var n_data = {
														id: callback.number[i],
														title: '<span>Неизвестный номер</span>',
														text: '<span>'+callback.number[i]+'</span>'
													};
									};
									self.popup(n_data);
								});	
							};
							if (callback.state[i] == 'Up' && callback.number[i] !== amoUsers[current_user].phone) {
								if(openwindows.indexOf(callback.number[i]) == -1) {
									$.get('//'+window.location.host+'/private/api/contact_search.php?SEARCH='+callback.number[i], function (contact) {
										if ($(contact).find('contact > id').eq(0).text().length > 0) {
											if ($(contact).find('contact > is_company').eq(0).text().indexOf('1') != -1){
												window.open('//'+window.location.host+'/companies/detail/'+$(contact).find('contact > id').eq(0).text());
												openwindows.push(callback.number[i])
											}
											else{
												window.open('//'+window.location.host+'/contacts/detail/'+$(contact).find('contact > id').eq(0).text());
												openwindows.push(callback.number[i])
											};
										}		
										else{
											window.open('//'+window.location.host+'/contacts/add/?phone='+callback.number[i]);
											openwindows.push(callback.number[i])
										};
									});	
								};
							};
						};
					});
				}, 5000);	
				self.add_action('phone', function (block) {
					
					var settings = self.params,
					current_user = AMOCRM.constant('user').id;
					settings.phones = JSON.parse(settings.phones);
					var amoUsers = {};
					for(var user in settings.phones) {
						amoUsers[user] = {};
						params = settings.phones[user].split(',');
							for(var i in params) {
								if (params[i].split('=')[1] !== undefined){
									amoUsers[user][params[i].split('=')[0]] = params[i].split('=')[1];
								}
								else {
									channel = params[i].split('=')[0];
										if(channel.split('/')[1] !== undefined) {
											amoUsers[user].protocol = channel.split('/')[0];
											amoUsers[user].phone = channel.split('/')[1];
										}
										else {
											amoUsers[user].phone = channel;
											amoUsers[user].protocol = 'SIP';
										};
								};
							};
					};
					
					
					
					if (amoUsers[current_user] !== undefined || amoUsers[current_user] !== '') {
						var channel = amoUsers[current_user].protocol + '/' amoUsers[current_user].phone;
						$.post(settings.scriptPath + '/api/call',{from:channel,to:block.value,as:'amocrm',context:amoUsers[current_user].context,variable:amoUsers[current_user].variable});
						var n_data = {
										id: 'TOCALL',
										title: '<span>Исходящий звонок</span>',
										text: '<span>'+block.value+'</span>'
									};
						self.popup(n_data);
						openwindows.push(n_data.id);
					};
					if (amoUsers[current_user] == undefined || amoUsers[current_user] == '') {
						if(openwindows.indexOf('CALL_ERROR') == -1) {
							var n_data = {
											id: 'CALL_ERROR',
											title: '<span>Кажется, возникла проблема</span>',
											text: '<span>Проверьте Ваш номер в настройках виджета</span>'
										};
							self.popup(n_data);
							openwindows.push(n_data.id);
						};
					};
				});
				
				return true;
			},
			bind_actions: function(){
				return true;
			},
			settings: function(){
				return true;
			},
			onSave: function(){
				return true;
			},
			destroy: function(){
			},
			contacts: {
					selected: function(){
					}
				},
			leads: {
					selected: function(){
					}
				},
			tasks: {
					selected: function(){
					}
				}
		};
		
		this.asteriskHandler = function(action_status) {
			var numbers = [],
				states = [];
			for (var i in action_status) {
				if((action_status[i].Channel.indexOf('/'+amoUsers[current_user].phone) !== -1) && (action_status[i].ChannelStateDesc == 'Ring'||'Up')) {
					numbers.push(action_status[i].ConnectedLineNum);
					states.push(action_status[i].ChannelStateDesc);
				};
			};
			var callback = {
							number: numbers,
							state: states
							};
			return callback;
		};
		
		this.popup = function (data) {	
			$('#popups_wrapper').append('<div class="popup-message window-body" id = "'+data.id+'"><div class="popup-message title-area">'+data.title+'</div><div class="popup-message text-area">'+data.text+'</div></div>');
			setTimeout(function(){
				$('#'+data.id).remove();
			}, 4500);	
			$('.popup-message').show(250, function(){
				setTimeout(function(){
					$('.popup-message').hide(250);
				}, 3000);
			});
		};
		return this;
    };
return CustomWidget;
});