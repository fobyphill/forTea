var timer4gla = 0


// выполнить проверку условия выполнения
function do_cc(json_object){
    $.ajax({url:'do-cc',
        method:'get',
        dataType:'json',
        data: {class_id: json_object.parent_structure, code: json_object.code},
        success:function(data){
            json_object['completion_condition'] = data
            $('#chb_cc').attr('checked', data)
            let b_del_style = (data) ? 'btn btn-danger' : 'tag-invis'
            $('#b_delete_object').attr('class', b_del_style)
        },
    })
}


// Получить наименование объекта аяксом. Вход: код объекта, айди класса тег для вывода
// class_type = t, c, d
function get_link_ajax(this_input, class_type='t') {
    clearTimeout(timer4gla)
    timer4gla = setTimeout(fast_get_link, 1000, this_input, class_type)
}



// glas = get_link_ajax_serch
function glas(this_input, class_type='t') {
    clearTimeout(timer4gla)
    timer4gla = setTimeout(()=>{
        let link_code = this_input.value
        let header_id = (this_input.id.slice(0,2) === 'sf') ? this_input.id.slice(2) : this_input.id.match(/.+sf(\d+)/)[1]
        let result = $('#link_sf' + header_id)[0]
        if (link_code === ''){
            let link = document.createElement('a')
            link.setAttribute('target', 'blank')
            let header = JSON.parse($('#header_info' + header_id).text())
            let header_val_def = ('value' in header) ? header.value : header.default
            let loc_class =  header_val_def.match(/(table|contract)\.(\d+)/)
            let url = (loc_class[1] === 'table') ? '/manage-object' : '/contract'
            url += '?class_id=' + loc_class[2]
            link.setAttribute('href', url)
            link.innerText = 'Перейти к объектам родителя'
            result.innerText = ''
            result.appendChild(link)
        }
        else{
            $.ajax({url:'query-link',
                method:'get',
                dataType:'json',
                data: {link_code: link_code, header_id: header_id, class_type: class_type},
                success:function(data){
                    if ('error' in data)
                        result.innerText = data.error
                    else{
                        let addr = (data.location[0] === 'c') ? 'contract' : 'manage-object'
                        let inner_text = (data.location === 'contract') ? date_time_to_rus(data.object_name) : data.object_name
                        result.innerHTML = '<a target="_blank" href="/' + addr + '?class_id=' + data.class_id + '&object_code='
                        + data.object_code + '">' + inner_text + '</a>'
                    }
                },
                error: function () {
                    result.innerText = 'Объект не найден'
                }
            })
        }
    }, 1000)
}


// Подсказка "ссылка"
function promp_link(this_input, is_contract=false) {
    clearTimeout(typingTimer);
    typingTimer = setTimeout(() =>{
        let link = this_input.value
        let header_id = this_input.id.match(/i_link_(\d+)/)[1]
        // let text_delay = (this_input.id.slice(this_input.id.length - 5) === 'delay') ? '_delay' : ''
        let result = $('#' + this_input.getAttribute('list'))[0]
        $.ajax({url:'promp-link',
            method:'get',
            dataType:'json',
            data: {link: link, header_id: header_id, is_contract: is_contract},
            success:function(data){
                result.innerText = ''
                data.forEach((d) =>{
                    let op = document.createElement('option')
                    op.value = d.code
                    op.innerText = d.value
                    result.appendChild(op)
                })
            },
            error: function () {
                result.innerText = ''
            }
        })
    }, 1200)
}

// Подсказка "ссылка" для поискового окна
// pls = promp_link_search
function pls(this_input, is_contract=false) {
    clearTimeout(typingTimer);
    typingTimer = setTimeout(() =>{
        let link = this_input.value
        let header_id = (this_input.id.slice(0,2) === 'sf') ? this_input.id.slice(2) : this_input.id.match(/.+sf(\d+)/)[1]
        let result = $('#dl_sf' + header_id)[0]
        $.ajax({url:'promp-link',
            method:'get',
            dataType:'json',
            data: {link: link, header_id: header_id, is_contract: is_contract},
            success:function(data){
                result.innerText = ''
                data.forEach((d) =>{
                    let op = document.createElement('option')
                    op.value = d.code
                    op.innerText = d.value
                    result.appendChild(op)
                })
            },
            error: function (err) {
                result.innerHTML = '<option value="error">' + err.responseText + '</option>'
            }
        })
    }, 800)
}


// вернуть список дат-пользователей из истории
// roh = return object history
function roh(class_id, code, location) {
    let timeline_from = $('#i_timeline_from').val()
    let timeline_to = $('#i_timeline_to').val()
    $.ajax({url:'roh',
        method:'get',
        dataType:'json',
        data: {class_id: class_id, code: code, location: location, timeline_from: timeline_from, timeline_to: timeline_to},
        success:function(data){
            let div_msg = $('#div_msg')
            if ('error' in data)
                div_msg.html(data.error).addClass('text-red')
            else{
                // оформим таймлайн
                let quantity_events = (data.timeline.length === 0) ? 0 : (data.timeline.length > 9) ? 9 : data.timeline.length - 1
                let i_hist_range = $('#i_hist_range')
                let steplist = $('#steplist')
                steplist.html('')
                for (let i = 1; i <= quantity_events; i++){
                    let op = document.createElement('option')
                    op.innerText = i
                    steplist.append(op)
                }
                i_hist_range.prop('max', quantity_events).val(quantity_events).attr('disable', false)
                // подкинем блок пагинации
                $('#div_timeline_pagination').remove()
                if (data.timeline.length > 10){
                    let page_count = Math.ceil(data.timeline.length / 10)
                    let div_pagination = document.createElement('div')
                    div_pagination.id = 'div_timeline_pagination'
                    div_pagination.className = "text-center mb-3"
                    let but_in_begin = document.createElement('button')
                    but_in_begin.className = 'like-a'
                    but_in_begin.innerHTML = '&nbsp;&lt;&lt;&nbsp;'
                    but_in_begin.id = 'b_tl_begin'
                    but_in_begin.setAttribute('onclick', 'go_timeline_page(' + page_count + ')')
                    div_pagination.appendChild(but_in_begin)
                    let but_prev = document.createElement('button')
                    but_prev.className = 'like-a'
                    but_prev.innerHTML = '&nbsp;&lt;&nbsp;'
                    but_prev.id = 'b_tl_prev'
                    but_prev.setAttribute('onclick', 'go_timeline_page(2)')
                    div_pagination.appendChild(but_prev)
                    let str = document.createElement('span')
                    str.innerHTML = " Страница <span id='s_tl_page_num'>1</span> из <span id='s_tl_page_quantity'>"
                        + page_count + "</span>"
                    str.id = 's_tl_pagination_info'
                    div_pagination.appendChild(str)
                    i_hist_range[0].parentNode.after(div_pagination)
                    let but_next = document.createElement('button')
                    but_next.className = 'tag-invis'
                    but_next.id = 'b_tl_next'
                    but_next.innerHTML = '&nbsp;&gt;&nbsp;'
                    div_pagination.appendChild(but_next)
                    let but_in_end = document.createElement('button')
                    but_in_end.className = 'tag-invis'
                    but_in_end.id = 'b_tl_end'
                    but_in_end.setAttribute('onclick', 'go_timeline_page(1)')
                    but_in_end.innerHTML = '&nbsp;&gt;&gt;&nbsp;'
                    div_pagination.appendChild(but_in_end)
                }
                array_timeline = data
                // Выведем последние даты таймлайна
                i_hist_range.val(i_hist_range.attr('max'))
                let last_event
                if (data.timeline.length){
                    let le = data.timeline[data.timeline.length - 1]
                    last_event = date_time_to_rus(le.date_update.slice(0, 19)) + ' ' + le.user
                }
                else last_event = date_time_to_rus(timeline_from)
                $('#s_hist_range').text(last_event)
                // Если мы находимся внутри истории, закроем для редактирование таймлайн планирования, выключим сохранение
                let tl_delay = $('#div_tl_delay')
                if (data.just_history){
                    $('#b_save').prop('disabled', true)
                    if (tl_delay.attr('class') !== 'tag-invis')
                        tl_delay.attr('class', 'div-disabled')
                    moove_time()
                }
                else{
                    $('#b_save').prop('disabled', false)
                    get_full_object(class_id, code, location)
                }
            }
        },
        error: function (data) {
            $('#s_object_hist').html('error')
            $('#s_hist_range').html('Ошибка')
            $('#div_msg').text('Ошибка: ' + data.responseText).attr('class', 'text-red')
        }
    })
}


// Пересчет алиаса
function recount_alias(this_select) {
    let header_id = this_select.id.match(/s_alias_(\d+)/)[1]
    let val = this_select.value
    let path = get_path_from_url()
    let is_contract = null
    if (['manage-object', 'table-draft'].includes(path))
        is_contract = false
    else if (path === 'tree'){
        if (get_param_from_url('location') === 'c')
            is_contract = true
    }
    else is_contract = true
    // let json_obj = ($('#s_object_hist').html()) ? $('#s_object_hist').html() : $('')

    // let is_contract = (JSON.parse($('#s_object_hist').html()).location === 'contract')
    let if_delay = (this_select.id.match(/s_alias_\d+_delay/)) ? '_delay' : ''
    let result = $('#div_alias_' + header_id + if_delay)
    $.ajax({url:'retreive-const',
        method:'get',
        dataType:'text',
        data: {header_id: header_id, val: val, is_contract: is_contract},
        success:function(data){
            result.html(data)
        },
        error: function () {
            result.html('error')
        }
    })
}


function fast_get_link(this_input,class_type='t'){
    let link_code = this_input.value
    let header_id = this_input.id.match(/i_link_(\d+)/)[1]
    let is_delay = (this_input.id.match(/i_link_\d+_delay/)) ? '_delay' : ''
    let result = $('#s_link_' + header_id + is_delay)[0]
    if (link_code === ''){
        let link = document.createElement('a')
        link.setAttribute('target', 'blank')
        let header = JSON.parse($('#header_info' + header_id).text())
        let loc_class = header.value.match(/(table|contract)\.(\d+)/)
        let url = (loc_class[1] === 'table') ? '/manage-object' : '/contract'
        url += '?class_id=' + loc_class[2]
        link.setAttribute('href', url)
        link.innerText = 'Перейти к объектам родителя'
        result.innerText = ''
        result.appendChild(link)
    }
    else{
        $.ajax({url:'query-link',
            method:'get',
            dataType:'json',
            data: {link_code: link_code, header_id: header_id, class_type: class_type},
            success:function(data){
                if ('error' in data)
                    result.innerText = data.error
                else{
                    let addr = (data.location[0] === 'c') ? 'contract' : 'manage-object'
                    let inner_text = (data.location === 'contract') ? date_time_to_rus(data.object_name) : data.object_name
                    result.innerHTML = '<a target="_blank" href="/' + addr + '?class_id=' + data.class_id + '&object_code='
                    + data.object_code + '">' + inner_text + '</a>'
                }
            },
            error: function () {
                result.innerText = 'Объект не найден'
            }
        })
    }
}


function get_tps(this_button){
    let array_id = this_button.id.slice(13)
    let timestamp = get_timestamp()[0]
    let array_codes = []
    json_object[array_id].objects.forEach(el => array_codes.push(el.code))
    $.ajax({url:'get-tps',
        method:'get',
        dataType:'json',
        data: {array_id: array_id, timestamp: timestamp, array_codes: JSON.stringify(array_codes)},
        success:function(data){
            let my_objs = json_object[array_id].objects
            for (let mo = 0; mo < my_objs.length; mo++){
                let my_obj = my_objs[mo]
                for (let i = 0; i < data.length; i++){
                    let tp = data[i]
                    let tp_obj = tp.objects.find(el => el.code === my_obj.code)
                    let tr = document.createElement('tr')
                    tr.className = 'row tr-tps-info'
                    tr.setAttribute('style', 'margin: 0;')
                    $('#trar_' +  array_id + '_' + my_obj.code)[0].after(tr)
                    let td_empty = document.createElement('td')
                    td_empty.className = 'col-1 bg-white'
                    tr.appendChild(td_empty)
                    let td_name = document.createElement('td')
                    td_name.className = 'col-4 text-center'
                    td_name.style = 'border: 1px solid #dee2e6'
                    td_name.innerHTML = 'ТП: ' + tp.name
                    tr.appendChild(td_name)
                    let td_data = document.createElement('td')
                    td_data.className = 'col'
                    td_data.setAttribute('style', 'padding: 0')
                    tr.appendChild(td_data)
                    let div_headers = document.createElement('div')
                    div_headers.className = 'row m-0'
                    td_data.appendChild(div_headers)
                    // заголовки
                    for (let k in tp){
                        if (['id', 'objects', 'name'].includes(k))
                            continue
                        let div_header = document.createElement('div')
                        div_header.className = 'col text-center p-0'
                        div_header.style = 'border: 1px solid #dee2e6'
                        div_header.innerText = tp[k]
                        div_headers.appendChild(div_header)
                    }
                    let div_vals = document.createElement('div')
                    div_vals.className = 'row m-0'
                    td_data.appendChild(div_vals)
                    for (let k in tp){
                        if (['id', 'objects', 'name'].includes(k))
                            continue
                        let div_val = document.createElement('div')
                        div_val.className = 'col text-center p-0'
                        div_val.style = 'border: 1px solid #dee2e6'
                        div_val.innerText = (k in tp_obj) ? tp_obj[k] : ''
                        div_vals.appendChild(div_val)
                    }
                }
            }
            // Итоги
            let tr_totals = document.createElement('tr')
            tr_totals.className = 'row m-0 tr-tps-info'
            let tbody_array = $('#tbody_array_' + array_id)
            tbody_array.append(tr_totals)
            let td_empty = document.createElement('td')
            td_empty.className = 'col-1 bg-white'
            tr_totals.appendChild(td_empty)
            let td_totals = document.createElement('td')
            td_totals.className = 'col py-0'
            td_totals.innerHTML = '<b>Итоги по техпроцессам</b>'
            tr_totals.appendChild(td_totals)
            for (let i = 0; i < data.length; i++){
                let tr = document.createElement('tr')
                tr.className = 'row m-0 tr-tps-info'
                tbody_array.append(tr)
                tr.appendChild(td_empty.cloneNode())
                let td_tp_name = document.createElement('td')
                td_tp_name.className = 'col-4 text-center'
                td_tp_name.style = 'border: 1px solid #dee2e6'
                td_tp_name.innerText = data[i].name
                tr.appendChild(td_tp_name)
                let td_tp_data = document.createElement('td')
                td_tp_data.className = 'col p-0'
                td_tp_data.style = 'border: 1px solid #dee2e6'
                tr.appendChild(td_tp_data)
                // Заголовки
                let div_headers = document.createElement('div')
                div_headers.className = 'row m-0'
                td_tp_data.appendChild(div_headers)
                for (let k in data[i]){
                    if (['id', 'objects', 'name'].includes(k))
                            continue
                    let div_header = document.createElement('div')
                    div_header.className = 'col text-center p-0'
                    div_header.style = 'border: 1px solid #dee2e6'
                    div_header.innerText = data[i][k]
                    div_headers.appendChild(div_header)
                }
                // Итоги
                let div_totals = document.createElement('div')
                div_totals.className = 'row m-0'
                td_tp_data.appendChild(div_totals)
                for (let k in data[i]){
                    if (['id', 'objects', 'name'].includes(k))
                            continue
                    let total = 0
                    let tot_objs = data[i].objects
                    for (let j = 0; j < tot_objs.length; j++)
                        total += (k in tot_objs[j]) ? tot_objs[j][k] : 0
                    let div_val = document.createElement('div')
                    div_val.className = 'col text-center p-0'
                    div_val.style = 'border: 1px solid #dee2e6'
                    div_val.innerText = total
                    div_totals.appendChild(div_val)
                }
            }
            // Работаем с кнопкой
            this_button.parentNode.parentNode.remove()
            let tr_button = document.createElement('tr')
            tr_button.className = 'row m-0 tr-tps-info bg-white'
            tbody_array.append(tr_button)
            let td_button = document.createElement('td')
            td_button.className = 'col p-0 text-center'
            tr_button.appendChild(td_button)
            let button_del = document.createElement('button')
            button_del.className = 'btn btn-link btn-sm'
            button_del.innerText = 'Удалить информацию о техпроцессах'
            button_del.setAttribute('onclick',  'del_tps(' + array_id + ')')
            td_button.appendChild(button_del)
        },
        error: function (data) {
            $('#div_msg').text('Ошибка: ' + data.responseText).attr('class', 'text-red')
        }
    })
}