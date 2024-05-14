// Переменные для таймера запуска аякса
var typingTimer;
var contract_biz_rule = true
var tps_valid_result = true
var update_stages_tp = {}
var tps_info = []
var new_tps_info = []
var tp_is_valid = true
var tp_modal = $('#tp_modal')

window.onload = function () {
    let tr = $('#data-table tr')
    if (tr.length){
        let table_active = $('#data-table tr.table-active')
        table_active.removeClass('table-active')
        if (table_active.length)
            // select_active_object(table_active[0])
            sao(table_active[0], 'c', true)
        else if (tr.length > 1)
            sao(tr[1], 'c', true)
    }
    start_popovers()
    fill_search_filter()  // Заполним фильтры поиска
}

// новый объект
function new_obj() {
    // чистим
    $('.table-active').removeClass('table-active')
    $('#i_code').val('')
    $('input[id*="date_time_record"]').val('')
    $("textarea[id*='ta_']").val('')
    $("input[id*='i_']").val('')
    $("input[id*='chb_']").attr('checked', false)
    $("span[id*='s_']").html('')
    $('label[id*="l_file_"]').html('Выберите файл')
    $('div[id*="div_formula_"]').html('')
    $("div[id*='div_table_slave_']").html('')
    $('#i_hist_range').val('').attr('max', '0')
    $('#steplist').html('')
    $('#div_timeline_pagination').remove()
    // чистим JSON-object
    for (let json_key in json_object){
        if (parseInt(json_key)){
            if ('value' in json_object[json_key])
                json_object[json_key].value = null
            if ('delay' in json_object[json_key])
                json_object[json_key].delay = null
        }
    }
    // Скрываем
    $("button[id*='b_save_']").attr('class', 'tag-invis')
    $("button[id*='b_del_']").attr('class', 'tag-invis')
    $('#div_tl_delay').attr('class', 'tag-invis')
    // покажем
    $('#b_save').attr('disabled', false)
    // Разблочим собственника
    let owner = $('a:contains("Собственник")')
    if (owner.length){
        let owner_id = owner[0].id.slice(8)
        $('#i_link_' + owner_id).attr('readonly', false).css('background-color', 'white')
    }
    // Получим техпроцессы
    tps = JSON.parse($('#tps').text())
    // Получим контрольные поля для техпроцессов
    let cfs = []
    tps.forEach(el => cfs.push(el.cf))
    // заполним дефолты
    $("span[id*='header_info']").toArray().forEach((elem) => {
        let id = elem.id.slice(11)
        let dict = JSON.parse(elem.innerHTML)
        // вычислим префикс
        let pref = ''
        if (['string', 'eval'].includes(dict.formula))
            pref = 'ta_'
        else if (dict.formula === 'enum')
            pref = 's_enum_'
        else if (dict.formula === 'date')
            pref = 'i_date_'
        else if (dict.formula === 'datetime')
            pref = 'i_datetime_'
        else if (dict.formula === 'float')
            pref = 'i_float_'
        else if (dict.formula === 'link')
            pref = 'i_link_'
        else if (dict.formula === 'bool')
            pref = 'chb_'
        else if (dict.formula === 'const')
            pref = 's_alias_'
        // вставим данные
        let current_node = $('#' + pref + id)
        if (dict.formula === 'const'){
            current_node.children().attr('selected', false)
            for (let i = 0; i < current_node.children().length; i++){
                if (current_node.children()[i].value === dict.default){
                    current_node.children()[i].setAttribute('selected', true)
                    break
                }
            }
        }
        else if (dict.formula === 'bool')
            current_node.prop('checked', (dict.default === 'True'))
        else if (dict.formula === 'enum')
            current_node[0].selectedIndex = 0
        else if (dict.formula === 'float'){
            current_node.val(dict.default)
            // Если данное поле является контрольным для техпроцессов - то запустим калькулятор ТПов
            if (tps.length && tps[0].control_field === parseInt(id)){
                $('input[id^="i_stage_"]').attr('readonly', true).val('')
                tps.forEach((el) => rfsot(current_node[0]))
            }
            if (cfs.includes(parseInt(id))){
                $('input[id^="i_stage_"]').attr('readonly', true).val('')
                reflofi(current_node[0], true)
            }
        }
        else current_node.val(dict.default)
        if (dict.formula === 'link')
            fast_get_link(current_node[0], 'c')
        // Заполним собственника для массивов
        let owner = $('input[name="input_owner"]')
        if (owner.length){
            let id = $("a:contains('Собственник')")[0].id.slice(8)
            $('#i_link_' + id).val(owner[0].value)
        }
    })
    $('#div_wrapper_dicts').html('')  // Удалим словари
    $('[id*=dict_info]').val('')  // Удалим информацию о текущих словарях
    $('#div_footer_dict').attr('class', 'input-group mb-3')  // Откроем выпадающий список
    // Заполним выпадающий список
    let select = $('#new_dict')[0]
    if (select)
        select.innerHTML = ''
    let headers_dict = $('[id*="header_dict"]').toArray()
    headers_dict.forEach((e) => {
        let json_obj = JSON.parse(e.innerText)
        let op = document.createElement('option')
        op.value = json_obj.id
        op.innerText = json_obj.name
        select.appendChild(op)
    })
    // изничтожим данные техпроцессов
    $('span[id^="s_stage_"]').html('')

}

function recount_tps(this_inp, is_set_interval=false) {
    let interval = (is_set_interval) ? 1000 : 0
    clearTimeout(typingTimer);
    typingTimer = setInterval(() => {
        let sum = (this_inp.value) ? parseFloat(this_inp.value) : 0
        let field_id = parseInt(this_inp.id.slice(8))
        let tps = JSON.parse($('#tps').text())
        // Проверим величину возврата
        let max_return = 0
        tps.forEach((el) => {
            if (el.cf_val === field_id){
                let current_sum = get_tp_currrent_sum(el.id)
                if (sum !== current_sum){
                    let delta = sum - current_sum
                    let first_stage = $('#i_stage_' + el.id + '_0')
                    let old_val = (first_stage.val()) ? parseFloat(first_stage.val()) : 0
                    let new_val = old_val + delta
                    if (new_val < 0){
                        delta_return = new_val * -1
                        if (delta_return > max_return)
                            max_return = delta_return
                    }
                }
            }
        })
        // Изменим первые стадии техпроцессов с учетом поправки вычитаемой суммы
        sum += max_return
        tps.forEach((el) => {
            if (el.cf_val === field_id){
                let current_sum = get_tp_currrent_sum(el.id)
                if (sum !== current_sum){
                    let delta = sum - current_sum
                    let first_stage = $('#i_stage_' + el.id + '_0')
                    let old_val = (first_stage.val()) ? parseFloat(first_stage.val()) : 0
                    first_stage.val(old_val + delta)
                    let first_delay = $('#s_stage_' + el.id + '_0_delay')
                    let old_delay = (first_delay.text()) ? parseFloat(first_delay.text()) : 0
                    first_delay.text(old_delay + delta)
                }
            }
        })
        this_inp.value = sum
    }, interval)
}

function get_tp_currrent_sum(tp_id) {
    let tag_stages = $('input[id^="i_stage_' + tp_id + '_"]').toArray()
    let current_sum = 0
    tag_stages.forEach((el) => {
        current_sum += (el.value) ? parseFloat(el.value) : 0
    })
    return current_sum
}

// rfsot = recount_first_stage_of_tp
function rfsot(control_field, is_delay, delta){
    let tps = json_object.new_tps
    for (let i = 0; i < tps.length; i++){
        if (tps[i].control_field !== control_field)
            continue
        let first_stage = tps[i].stages[0]
        let fact = $('#s_stage_' + first_stage.id + '_fact')
        let fact_val = (fact.text().length) ? parseFloat(fact.text()) : 0
        let delay = $('#s_stage_' + first_stage.id + '_delay')
        let delay_val = (delay.text()) ? parseFloat(delay.text()) : 0
        if (is_delay)
            delay.text(delay_val + delta)
        else fact.text(fact_val + delta)
        $('#i_stage_' + first_stage.id).val(fact_val + delay_val + delta)
    }
}

function csot(stage_id, tp_id) {
    clearTimeout(typingTimer)
    typingTimer = setTimeout(()=>{
        if (!new_tps_info.length)
            new_tps_info = JSON.parse($('#tps').text())
        let tp_info = new_tps_info.find(el => el.id === tp_id)
        let tp = json_object.new_tps.find(el => el.id === tp_id)
        let state_cf = $('#s_' + tp.control_field + '_state')
        let old_val
        if (state_cf.length)
            old_val = (state_cf.text()) ? parseFloat(state_cf.text()) : 0
        else{
            let old_fact = $('#i_float_' + tp.control_field)
            old_val = (old_fact.val()) ? parseFloat(old_fact.val()) : 0
        }
        let new_val = 0
        for (let i = 0; i < tp.stages.length; i++){
            let state = $('#i_stage_' + tp.stages[i].id)
            if (state.val())
                new_val += parseFloat(state.val())
        }
        let delta = new_val - old_val
        let this_input = $('#i_stage_' + stage_id)[0]
        let current_stage_val = (this_input.value) ? parseFloat(this_input.value) : 0
        this_input.defaultValue = (current_stage_val) - delta

        let work_with_parents = true
        if (!delta)
            return false
        else if (delta < 0)
            work_with_parents = false

        // Если первая стадия увеличилась - просто все возвращаем на свои места (увеличить первую стадию можно только из КП)
        if (stage_id === tp_info.stages[0].id && work_with_parents){
            this_input.value = this_input.defaultValue
            this_input.defaultValue = ''
            return false
        }
        let my_stage = tp.stages.find(el => el.id === stage_id)
        // обновленная функция cd - cascad deduction
        function cd(stage, delta){
            let partners
            if (work_with_parents)
                partners = tp_info.stages.filter(el => el.value.children.includes(stage.id) && el !== my_stage)
            else{
                let children = tp_info.stages.find(el => el.id === stage.id).value.children
                partners = tp_info.stages.filter(el => children.includes(el.id) && el !== my_stage)
            }
            if (!partners.length)
                return [true, delta]
            if (partners.length === 1){
                let rest = 0
                update_stages_tp[partners[0].id] = {}
                let partner_state = $('#i_stage_' + partners[0].id)
                let partner_state_val = (partner_state.val()) ? parseFloat(partner_state.val()) : 0
                update_stages_tp[partners[0].id].value = partner_state_val
                if (work_with_parents){
                    let partner_start_delay = $('#s_stage_' + partners[0].id + '_start_delay')
                    let partner_start_delay_val = (partner_start_delay.text()) ? parseFloat(partner_start_delay.text()) : 0
                    let min_state = (partner_start_delay_val < 0) ? partner_state_val : partner_state_val - partner_start_delay_val
                    if (delta > min_state){
                        rest = delta - min_state
                        delta = min_state
                    }
                }
                else{
                    let my_start_delay = $('#s_stage_' + stage.id + '_start_delay')
                    let my_start_delay_val = (my_start_delay.text()) ? parseFloat(my_start_delay.text()) : 0
                    let my_state = $('#i_stage_' + stage.id)
                    let my_state_val = (my_state.val()) ? parseFloat(my_state.val()) : 0
                    let oper_fact = my_state_val - my_start_delay_val
                    if (oper_fact < 0){
                        rest = oper_fact
                        delta -= oper_fact
                    }
                }
                update_stages_tp[partners[0].id].value -= delta
                return [true, rest]
            }
            else {
                // готовим модальное окно
                if (!(partners[0].id in update_stages_tp)){
                    let text_parent_child = (work_with_parents) ? 'родительской' : 'дочерней'
                    $('#s_tp_modal_header').text('У стадии техпрпоцесса "' + stage.name + '" более одной ' + text_parent_child + ' стадии')
                    let modal_body = $('#d_tp_modal_body')
                    let header = 'Выберите стадии для взаимодействия<br />'
                    modal_body.html(header)
                    // Готовим таблицу в окно
                    let table = document.createElement('table')
                    table.style = 'width: 100%'
                    modal_body.append(table)
                    let table_header = document.createElement('tr')
                    table_header.className = 'row text-bold text-center'
                    table.appendChild(table_header)
                    let header_name = document.createElement('td')
                    header_name.className = 'col'
                    table_header.appendChild(header_name)
                    let old_state = document.createElement('td')
                    old_state.className = 'col'
                    old_state.innerText = 'State'
                    table_header.appendChild(old_state)
                    let th_delta = document.createElement('td')
                    th_delta.className = 'col'
                    th_delta.innerText = 'Разность'
                    table_header.appendChild(th_delta)
                    update_stages_tp.tech_pro_id = tp_id
                    update_stages_tp.control_val = delta * -1
                    update_stages_tp.current_stage = stage
                    for (let i = 0; i < partners.length; i++){
                        let tr = document.createElement('tr')
                        tr.className = 'row'
                        table.appendChild(tr)
                        let td_name = document.createElement('td')
                        td_name.className = 'col my-auto'
                        td_name.innerText = partners[i].name
                        tr.appendChild(td_name)
                        let td_state = document.createElement('td')
                        td_state.className = 'col form-control text-right bg-light'
                        let partner = $('#i_stage_' + partners[i].id)
                        td_state.innerText = partner.val()
                        tr.appendChild(td_state)
                        let td_delta = document.createElement('td')
                        td_delta.className = 'col'
                        tr.appendChild(td_delta)
                        let inp = document.createElement('input')
                        inp.className = 'form-control text-right'
                        inp.type = 'number'
                        inp.id = 'i_st_' + partners[i].id + '_delta'
                        inp.setAttribute('oninput', 'tp_alert_calc()')
                        let current_stage = (partner.val()) ? parseFloat(partner.val()) : 0
                        if (delta > 0 && delta > current_stage) {
                            delta -= current_stage
                            current_stage *= -1
                        }
                        else {
                            current_stage = delta * -1
                            delta = 0
                        }
                        inp.value = current_stage
                        td_delta.appendChild(inp)
                    }
                    $('#tp_modal').modal('show')
                    tp_is_valid = false
                    return [false, delta]
                }
                // обрабатываем введенные ранее данные
                else{
                    delta = 0
                    for (let i = 0; i < partners.length; i++){
                        let local_delta = update_stages_tp[partners[i].id].delta * -1
                        let partner_start_delay = $('#s_stage_' + partners[i].id + '_start_delay')
                        let partner_start_delay_val = (partner_start_delay.text()) ? parseFloat(partner_start_delay.text()) : 0
                        let partner_state = $('#i_stage_' + partners[i].id)
                        let partner_state_val = (partner_state.val()) ? parseFloat(partner_state.val()) : 0
                        let min_state = (partner_start_delay_val < 0) ? partner_state_val : partner_state_val - partner_start_delay_val
                        if (local_delta > min_state){
                            delta += local_delta - min_state
                            update_stages_tp[partners[i].id].value += delta
                        }
                    }
                }
                return [true, delta]
            }
        }
        let rest = cd(my_stage, delta)
        // Выполняем каскадное заполнение стадий
        if (rest[0]){
            for (let ust in update_stages_tp){
                let state = $('#i_stage_' + ust)
                state.val(update_stages_tp[ust].value)
                let fact = $('#s_stage_' + ust + '_fact')
                let fact_val = (fact.text()) ? parseFloat(fact.text()) : 0
                $('#s_stage_' + ust + '_delay').text(update_stages_tp[ust].value - fact_val)
            }
            this_input.value = current_stage_val - rest[1]
            update_stages_tp = {}
            this_input.defaultValue = ''
            // Заполним делэй
            let fact = $('#s_stage_' + stage_id + '_fact')
            let fact_val = (fact.text()) ? parseFloat(fact.text()) : 0
            $('#s_stage_' + stage_id + '_delay').text(current_stage_val - rest[1] - fact_val)
        }
    }, 1000)
}


function old_csot(stage_id, tp_id) {
    clearTimeout(typingTimer)
    typingTimer = setTimeout(()=>{
        if (!new_tps_info.length)
            new_tps_info = JSON.parse($('#tps').text())
        let tp_info = new_tps_info.find(el => el.id === tp_id)
        let tp = json_object.new_tps.find(el => el.id === tp_id)
        let state_cf = $('#s_' + tp.control_field + '_state')
        let old_val
        if (state_cf.length)
            old_val = (state_cf.text()) ? parseFloat(state_cf.text()) : 0
        else{
            let old_fact = $('#i_float_' + tp.control_field)
            old_val = (old_fact.val()) ? parseFloat(old_fact.val()) : 0
        }
        let new_val = 0
        for (let i = 0; i < tp.stages.length; i++){
            let state = $('#i_stage_' + tp.stages[i].id)
            if (state.val())
                new_val += parseFloat(state.val())
        }
        let delta = new_val - old_val
        let this_input = $('#i_stage_' + stage_id)[0]
        let current_stage_val = (this_input.value) ? parseFloat(this_input.value) : 0
        this_input.defaultValue = (current_stage_val) - delta

        let work_with_parents = true
        if (!delta)
            return false
        else if (delta < 0)
            work_with_parents = false

        // Если первая стадия увеличилась - просто все возвращаем на свои места (увеличить первую стадию можно только из КП)
        if (stage_id === tp_info.stages[0].id && work_with_parents){
            this_input.value = this_input.defaultValue
            this_input.defaultValue = ''
            return false
        }
        let my_stage = tp.stages.find(el => el.id === stage_id)
        // Временно не использую каскадное исчерпание
        function cascad_deduction(stage, delta) {
            let rest = 0
            let parent_name = get_parent(stage)
            if (!parent_name)
                return -1
            let parent_num = tp.stages.findIndex((el) => el.name === parent_name)
            let parent_el = tp.stages[parent_num]
            let parent_old_val = (parent_el.value) ? parseFloat(parent_el.value) : 0
            let parent_new_val = parent_old_val - delta
            update_stages_tp[stage].num = parent_num
            if (parent_new_val >= 0)
                update_stages_tp[stage].value = parent_new_val
            else {
                update_stages_tp[stage].value = 0
                if (parent_num)
                    rest = cascad_deduction(parent_name, parent_new_val * -1)
                else rest = parent_new_val * -1
            }
            return rest
        }
        // обновленная функция cd - cascad deduction
        function cd(stage, delta){
            let partners
            if (work_with_parents)
                partners = tp_info.stages.filter(el => el.value.children.includes(stage.id) && el !== my_stage)
            else{
                let children = tp_info.stages.find(el => el.id === stage.id).value.children
                partners = tp_info.stages.filter(el => children.includes(el.id) && el !== my_stage)
            }
            if (!partners.length)
                return [true, delta]
            if (partners.length === 1){
                if (partners[0].id in update_stages_tp)
                    delta -= update_stages_tp[partners[0].id].value
                else{
                    update_stages_tp[partners[0].id] = {}
                    // let partner_num = tp.stages.value.findIndex((el) => el === partners[0].name)
                    // update_stages_tp[partners[0].id].num = partner_num
                    // let partner_fact = $('#s_stage_' + partners[0].id + '_fact')
                    // let partner_fact_val = (partner_fact.text()) ? parseFloat(partner_fact.text()) : 0
                    let partner_state = $('#i_stage_' + partners[0].id )
                    let partner_state_val = (partner_state.val()) ? parseFloat(partner_state.val()) : 0
                    if (delta > 0 && delta > partner_state_val){
                        delta -= partner_state_val
                        partner_state_val -= partner_state_val
                    }
                    else {
                        partner_state_val -= delta
                        delta = 0
                    }
                    update_stages_tp[partners[0].id].value = partner_state_val
                }
                if (delta){
                    let granny = tp_info.stages.filter(el => el.value.children.includes(partners[0].id) && el.id !== my_stage.id
                                                   && !(el.id in update_stages_tp))
                    if (granny.length)
                        delta = cd(partners[0].id, delta)[1]
                }
                return [true, delta]
            }
            else {
                // готовим модальное окно
                if (!(partners[0].id in update_stages_tp)){
                    let text_parent_child = (work_with_parents) ? 'родительской' : 'дочерней'
                    $('#s_tp_modal_header').text('У стадии техпрпоцесса "' + stage.name + '" более одной ' + text_parent_child + ' стадии')
                    let modal_body = $('#d_tp_modal_body')
                    let header = 'Выберите стадии для взаимодействия<br />'
                    modal_body.html(header)
                    // Готовим таблицу в окно
                    let table = document.createElement('table')
                    table.style = 'width: 100%'
                    modal_body.append(table)
                    let table_header = document.createElement('tr')
                    table_header.className = 'row text-bold text-center'
                    table.appendChild(table_header)
                    let header_name = document.createElement('td')
                    header_name.className = 'col'
                    table_header.appendChild(header_name)
                    let old_state = document.createElement('td')
                    old_state.className = 'col'
                    old_state.innerText = 'State'
                    table_header.appendChild(old_state)
                    let th_delta = document.createElement('td')
                    th_delta.className = 'col'
                    th_delta.innerText = 'Разность'
                    table_header.appendChild(th_delta)
                    update_stages_tp.tech_pro_id = tp_id
                    update_stages_tp.control_val = delta * -1
                    update_stages_tp.current_stage = stage
                    for (let i = 0; i < partners.length; i++){
                        let tr = document.createElement('tr')
                        tr.className = 'row'
                        table.appendChild(tr)
                        let td_name = document.createElement('td')
                        td_name.className = 'col my-auto'
                        td_name.innerText = partners[i].name
                        tr.appendChild(td_name)
                        let td_state = document.createElement('td')
                        td_state.className = 'col form-control text-right bg-light'
                        let partner = $('#i_stage_' + partners[i].id)
                        td_state.innerText = partner.val()
                        tr.appendChild(td_state)
                        let td_delta = document.createElement('td')
                        td_delta.className = 'col'
                        tr.appendChild(td_delta)
                        let inp = document.createElement('input')
                        inp.className = 'form-control text-right'
                        inp.type = 'number'
                        inp.id = 'i_st_' + partners[i].id + '_delta'
                        inp.setAttribute('oninput', 'tp_alert_calc()')
                        let current_stage = (partner.val()) ? parseFloat(partner.val()) : 0
                        if (delta > 0 && delta > current_stage) {
                            delta -= current_stage
                            current_stage *= -1
                        }
                        else {
                            current_stage = delta * -1
                            delta = 0
                        }
                        inp.value = current_stage
                        td_delta.appendChild(inp)
                    }
                    $('#tp_modal').modal('show')
                    tp_is_valid = false
                    return [false, delta]
                }
                // обрабатываем введенные ранее данные
                else{
                    for (let i = 0; i < partners.length; i++){
                        delta += update_stages_tp[partners[i].id].delta
                        if (!delta)
                            break
                    }
                    for (let j = 0; j < partners.length; j++){
                        if (delta){
                            let granny = tp.stages.filter(el => el.children.includes(partners[j].id) && el.id !== my_stage.id
                                                   && !(el.id in update_stages_tp))
                            if (granny.length)
                                delta = cd(partners[j].name, delta)[1]
                        }
                        else break
                    }
                }
                return [true, delta]
            }
        }
        let rest = cd(my_stage, delta)
        // Выполняем каскадное заполнение стадий
        if (rest[0]){
            for (let ust in update_stages_tp){
                let state = $('#i_stage_' + ust)
                state.val(update_stages_tp[ust].value)
                let fact = $('#s_stage_' + ust + '_fact')
                let fact_val = (fact.text()) ? parseFloat(fact.text()) : 0
                $('#s_stage_' + ust + '_delay').text(update_stages_tp[ust].value - fact_val)
            }
            this_input.value = current_stage_val - rest[1]
            update_stages_tp = {}
            this_input.defaultValue = ''
            // Заполним делэй
            let fact = $('#s_stage_' + stage_id + '_fact')
            let fact_val = (fact.text()) ? parseFloat(fact.text()) : 0
            $('#s_stage_' + stage_id + '_delay').text(current_stage_val - rest[1] - fact_val)
        }
    }, 1000)
}

function choice_parent(){
    $('input[id^="i_st_"]').each(function(){
        let my_id = parseInt($(this)[0].id.match(/i_st_(\d+)_delta/)[1])
        let my_delta = ($(this).val()) ? parseFloat($(this).val()) : 0
        update_stages_tp[my_id] = {}
        let old_val = $('#i_stage_' + my_id).val()
        old_val = (old_val) ? parseFloat(old_val) : 0
        update_stages_tp[my_id].value = old_val + my_delta
        update_stages_tp[my_id].delta = my_delta
    })
    tp_is_valid = true
    tp_modal.modal('hide')
    csot(update_stages_tp.current_stage.id, update_stages_tp.tech_pro_id)
}

// проверка корректности закрытия модального окна
tp_modal.on('hidden.bs.modal', function (e) {
  if (!tp_is_valid){
      $('input[id^="i_stage_"]').each(function(){
          if (this.defaultValue){
              this.value = this.defaultValue
              this.defaultValue = ''
              update_stages_tp = {}
          }
      })
  }
})

// проверка корректности данных модального окна
function tp_alert_calc(){
    let sum = 0
    $('input[id^="i_st_"]').each(function(){
        sum += 1* $(this).val()
    })
    $('#b_tp_ok').attr('disabled', (sum !== update_stages_tp.control_val))
}


