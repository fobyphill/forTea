var new_tps_info = []
var update_stages_tp = {}
var tps_valid_result = true
var tp_is_valid = true
var tp_modal = $('#tp_modal')
var stages_modal = $('input[id^="i_st_delta_"]')
var set_movs = []


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

// Показать возможные варианты перемещения из стадии ТП в стадию - устарела. Удалить после 01.04.2025
// function csot(stage_id, tp_id) {
//     clearTimeout(typingTimer)
//     typingTimer = setTimeout(()=>{
//         if (!new_tps_info.length)
//             new_tps_info = JSON.parse($('#tps').text())
//         let tp_info = new_tps_info.find(el => el.id === tp_id)
//         let tp = json_object.new_tps.find(el => el.id === tp_id)
//         let state_cf = $('#s_' + tp.control_field + '_state')
//         let old_val
//         if (state_cf.length)
//             old_val = (state_cf.text()) ? parseFloat(state_cf.text()) : 0
//         else{
//             let old_fact = $('#i_float_' + tp.control_field)
//             old_val = (old_fact.val()) ? parseFloat(old_fact.val()) : 0
//         }
//         let new_val = 0
//         for (let i = 0; i < tp.stages.length; i++){
//             let state = $('#i_stage_' + tp.stages[i].id)
//             if (state.val())
//                 new_val += parseFloat(state.val())
//         }
//         let delta = new_val - old_val
//         let this_input = $('#i_stage_' + stage_id)[0]
//         let current_stage_val = (this_input.value) ? parseFloat(this_input.value) : 0
//         this_input.defaultValue = (current_stage_val) - delta
//         let work_with_parents = true
//         if (!delta)
//             return false
//         else if (delta < 0)
//             work_with_parents = false
//
//         // Если первая стадия увеличилась - просто все возвращаем на свои места (увеличить первую стадию можно только из КП)
//         if (stage_id === tp_info.stages[0].id && work_with_parents){
//             this_input.value = this_input.defaultValue
//             this_input.defaultValue = ''
//             return false
//         }
//         let my_stage = tp.stages.find(el => el.id === stage_id)
//         // обновленная функция cd - cascad deduction
//         function cd(stage, delta){
//             let partners
//             if (work_with_parents)
//                 partners = tp_info.stages.filter(el => el.value.children.includes(stage.id) && el !== my_stage)
//             else{
//                 let children = tp_info.stages.find(el => el.id === stage.id).value.children
//                 partners = tp_info.stages.filter(el => children.includes(el.id) && el !== my_stage)
//             }
//             if (!partners.length)
//                 return [true, delta]
//             if (partners.length === 1){
//                 let rest = 0
//                 update_stages_tp[partners[0].id] = {}
//                 let partner_state = $('#i_stage_' + partners[0].id)
//                 let partner_state_val = (partner_state.val()) ? parseFloat(partner_state.val()) : 0
//                 update_stages_tp[partners[0].id].value = partner_state_val
//                 if (work_with_parents){
//                     let partner_start_delay = $('#s_stage_' + partners[0].id + '_start_delay')
//                     let partner_start_delay_val = (partner_start_delay.text()) ? parseFloat(partner_start_delay.text()) : 0
//                     let min_state = (partner_start_delay_val < 0) ? partner_state_val : partner_state_val - partner_start_delay_val
//                     if (delta > min_state){
//                         rest = delta - min_state
//                         delta = min_state
//                     }
//                 }
//                 else{
//                     let my_start_delay = $('#s_stage_' + stage.id + '_start_delay')
//                     let my_start_delay_val = (my_start_delay.text()) ? parseFloat(my_start_delay.text()) : 0
//                     let my_state = $('#i_stage_' + stage.id)
//                     let my_state_val = (my_state.val()) ? parseFloat(my_state.val()) : 0
//                     let oper_fact = my_state_val - my_start_delay_val
//                     if (oper_fact < 0){
//                         rest = oper_fact
//                         delta -= oper_fact
//                     }
//                 }
//                 update_stages_tp[partners[0].id].value -= delta
//                 return [true, rest]
//             }
//             else {
//                 // готовим модальное окно
//                 if (!(partners[0].id in update_stages_tp)){
//                     let text_parent_child = (work_with_parents) ? 'родительской' : 'дочерней'
//                     $('#s_tp_modal_header').text('У стадии техпрпоцесса "' + stage.name + '" более одной ' + text_parent_child + ' стадии')
//                     let modal_body = $('#d_tp_modal_body')
//                     let header = 'Выберите стадии для взаимодействия<br />'
//                     modal_body.html(header)
//                     // Готовим таблицу в окно
//                     let table = document.createElement('table')
//                     table.style = 'width: 100%'
//                     modal_body.append(table)
//                     let table_header = document.createElement('tr')
//                     table_header.className = 'row text-bold text-center'
//                     table.appendChild(table_header)
//                     let header_name = document.createElement('td')
//                     header_name.className = 'col'
//                     table_header.appendChild(header_name)
//                     let old_state = document.createElement('td')
//                     old_state.className = 'col'
//                     old_state.innerText = 'State'
//                     table_header.appendChild(old_state)
//                     let th_delta = document.createElement('td')
//                     th_delta.className = 'col'
//                     th_delta.innerText = 'Разность'
//                     table_header.appendChild(th_delta)
//                     update_stages_tp.tech_pro_id = tp_id
//                     update_stages_tp.control_val = delta * -1
//                     update_stages_tp.current_stage = stage
//                     for (let i = 0; i < partners.length; i++){
//                         let tr = document.createElement('tr')
//                         tr.className = 'row'
//                         table.appendChild(tr)
//                         let td_name = document.createElement('td')
//                         td_name.className = 'col my-auto'
//                         td_name.innerText = partners[i].name
//                         tr.appendChild(td_name)
//                         let td_state = document.createElement('td')
//                         td_state.className = 'col form-control text-right bg-light'
//                         let partner = $('#i_stage_' + partners[i].id)
//                         td_state.innerText = partner.val()
//                         tr.appendChild(td_state)
//                         let td_delta = document.createElement('td')
//                         td_delta.className = 'col'
//                         tr.appendChild(td_delta)
//                         let inp = document.createElement('input')
//                         inp.className = 'form-control text-right'
//                         inp.type = 'number'
//                         inp.id = 'i_st_' + partners[i].id + '_delta'
//                         inp.setAttribute('oninput', 'tp_alert_calc()')
//                         let current_stage = (partner.val()) ? parseFloat(partner.val()) : 0
//                         if (delta > 0 && delta > current_stage) {
//                             delta -= current_stage
//                             current_stage *= -1
//                         }
//                         else {
//                             current_stage = delta * -1
//                             delta = 0
//                         }
//                         inp.value = current_stage
//                         td_delta.appendChild(inp)
//                     }
//                     tp_alert_calc()
//                     $('#tp_modal').modal('show')
//                     tp_is_valid = false
//                     return [false, delta]
//                 }
//                 // обрабатываем введенные ранее данные
//                 else{
//                     delta = 0
//                     for (let i = 0; i < partners.length; i++){
//                         let local_delta = update_stages_tp[partners[i].id].delta * -1
//                         let partner_start_delay = $('#s_stage_' + partners[i].id + '_start_delay')
//                         let partner_start_delay_val = (partner_start_delay.text()) ? parseFloat(partner_start_delay.text()) : 0
//                         let partner_state = $('#i_stage_' + partners[i].id)
//                         let partner_state_val = (partner_state.val()) ? parseFloat(partner_state.val()) : 0
//                         let min_state = (partner_start_delay_val < 0) ? partner_state_val : partner_state_val - partner_start_delay_val
//                         if (local_delta > min_state){
//                             delta += local_delta - min_state
//                             update_stages_tp[partners[i].id].value += delta
//                         }
//                     }
//                 }
//                 return [true, delta]
//             }
//         }
//         let rest = cd(my_stage, delta)
//         // Выполняем каскадное заполнение стадий
//         if (rest[0]){
//             for (let ust in update_stages_tp){
//                 let state = $('#i_stage_' + ust)
//                 state.val(update_stages_tp[ust].value)
//                 let fact = $('#s_stage_' + ust + '_fact')
//                 let fact_val = (fact.text()) ? parseFloat(fact.text()) : 0
//                 $('#s_stage_' + ust + '_delay').text(update_stages_tp[ust].value - fact_val)
//             }
//             this_input.value = current_stage_val - rest[1]
//             update_stages_tp = {}
//             this_input.defaultValue = ''
//             // Заполним делэй
//             let fact = $('#s_stage_' + stage_id + '_fact')
//             let fact_val = (fact.text()) ? parseFloat(fact.text()) : 0
//             $('#s_stage_' + stage_id + '_delay').text(current_stage_val - rest[1] - fact_val)
//         }
//     }, 1000)
// }


// shvast = show_vars_stages
function shvast(this_input, stage_id, tp_id){
    clearTimeout(typingTimer)
    typingTimer = setTimeout(() =>{
        if (!new_tps_info.length)
            new_tps_info = JSON.parse($('#tps').text())
        let tp_info = new_tps_info.find(el => el.id === tp_id)
        let tp = json_object.new_tps.find(el => el.id === tp_id)
        let my_stage = tp.stages.find(el => el.id === stage_id)
        let stage_info = tp_info.stages.find(el => el.id === stage_id)
        let old_stage = my_stage.value.fact + my_stage.value.delay.reduce((a, b) => a + b.value, 0)
        let new_val = parseFloat(this_input.value)
        let delta = new_val - old_stage
        let partner = (delta > 0) ? tp_info.stages.find(el => el.value.children.includes(stage_id)) :
            tp.stages.find(el => stage_info.value.children.includes(el.id))

        // Проверка. Не увеличиваем ли первую стадию
        if (tp.stages[0] === my_stage && delta > 0){
            this_input.value = old_stage
            return
        }
        // Рисуем модальное окно
        $('#s_tp_modal_header').text('Перемещение внутри техпроцесса')
        let modal_body = $('#d_tp_modal_body')
        let header = 'Выберите стадии для взаимодействия<br />'
        modal_body.html(header)
        // Готовим таблицу в окно
        let table = document.createElement('table')
        table.className = 'w-100'
        table.id = 'table_deltas_modal_' + tp_id
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
        for (let i = 0; i < tp_info.stages.length; i++){
            let tr = document.createElement('tr')
            tr.className = 'row'
            table.appendChild(tr)
            let td_name = document.createElement('td')
            td_name.className = 'col my-auto'
            td_name.innerText = tp_info.stages[i].name
            tr.appendChild(td_name)
            let td_state = document.createElement('td')
            td_state.className = 'col form-control text-right bg-light'
            td_state.innerText = tp.stages[i].value.fact + tp.stages[i].value.delay.reduce((a, b) => a + b.value, 0)
            tr.appendChild(td_state)
            let td_delta = document.createElement('td')
            td_delta.className = 'col'
            tr.appendChild(td_delta)
            let inp = document.createElement('input')
            inp.className = 'form-control text-right'
            inp.type = 'number'
            inp.id = 'i_st_delta_' + tp_info.stages[i].id
            if (tp_info.stages[i].id === stage_id)
                inp.value = delta
            else if (tp_info.stages[i].id === partner.id)
                inp.value = delta * -1
            inp.setAttribute('oninput', 'tp_alert_calc()')
            td_delta.appendChild(inp)
        }
        $('#tp_modal').modal('show')

    }, 1000)
}


function cancel_change_tp(){
    let tp_id
    let table_deltas = $("[id^='table_deltas_modal_']")
    if (table_deltas.length)
        tp_id = table_deltas[0].id.slice(19)
    else{
        let radio_rout = $('input[type="radio"][id^="r_"]')
        if (radio_rout.length)
            tp_id = radio_rout[0].id.match(/r_(\d+)_/)[1]
        else{
            let header_set_movs = $('[id^="h_set_movs_"]')
            if (header_set_movs.length)
                tp_id = header_set_movs[0].id.slice(11)
        }
    }
    tp_id = parseInt(tp_id)
    let my_tp = json_object.new_tps.find(el => el.id === tp_id)
    for (let i = 0; i < my_tp.stages.length; i++){
        let val = my_tp.stages[i].value.fact + my_tp.stages[i].value.delay.reduce((a, b) => a + b.value, 0)
        if (val === 0)
            val = ''
        $("#i_stage_" + my_tp.stages[i].id).val(val)
    }
}


// проверка корректности данных модального окна
function tp_alert_calc(){
    let sum = 0
    let is_deltas = false
    $('input[id^="i_st_"]').each(function(){
        let this_val = 1 * $(this).val()
        sum += this_val
        if (this_val)
            is_deltas = true
    })
    $('#b_tp_ok').attr('disabled', (sum !== 0 && is_deltas))
}


function get_routs(){
    let tp_id
    let table_deltas = $('[id^="table_deltas_modal_"]')
    if (table_deltas.length)
        tp_id = parseInt(table_deltas[0].id.slice(19))
    else{
        let radio_routs = $('input[id^="r_"]')
        if (radio_routs.length)
            tp_id = parseInt(radio_routs[0].id.slice(2))
        else return
    }
    let tp_info = new_tps_info.find(el => el.id === tp_id)
    stages_modal = $('input[id^="i_st_delta_"]')
    if (!stages_modal.length)
        save_movs(tp_id)
    let parents = []
    let offspring = []
    for (let i = 0; i < stages_modal.length; i++){
        let dict_stage_val = {'id': parseInt(stages_modal[i].id.slice(11)), 'val': parseFloat(stages_modal[i].value)}
        if (dict_stage_val.val < 0)
            parents.push(dict_stage_val)
        else if (dict_stage_val.val > 0)
            offspring.push(dict_stage_val)
    }
    let div_body = $('#d_tp_modal_body')
    div_body.html('')
    let parent_permutations = permutations(parents)
    let offspring_perms = permutations(offspring)
    set_movs = []
    for (let d = 0; d < parent_permutations.length; d++){
        for (let i = 0; i < offspring_perms.length; i++){
            let array_movs = []
            let pa_pe = structuredClone(parent_permutations[d])
            let clone_offs = structuredClone(offspring_perms[i])
            for (let j = 0; j < pa_pe.length; j++){
                for (let k = 0; k < clone_offs.length;  k++){
                    if (pa_pe[j].val === 0)
                        break
                    if (clone_offs[k].val === 0)
                        continue
                    let dict_mov = {'parent_id': pa_pe[j].id, 'offspring_id': clone_offs[k].id}
                    let abs_parent = pa_pe[j].val * -1
                    if (abs_parent >= clone_offs[k].val){
                        dict_mov.delta = clone_offs[k].val
                        pa_pe[j].val += clone_offs[k].val
                        clone_offs[k].val = 0
                    }
                    else{
                        dict_mov.delta = abs_parent
                        pa_pe[j].val = 0
                        clone_offs[k].val -= abs_parent
                    }
                    array_movs.push(dict_mov)
                }
            }
            array_movs.sort((a, b) => a.parent_id - b.parent_id || a.offspring_id - b.offspring_id)
            let array_absent = true
            for (let j = 0; j < set_movs.length; j++){
                if (arrays_equal(set_movs[j], array_movs)){
                    array_absent = false
                    break
                }
            }
            if (array_absent)
                set_movs.push(array_movs)
        }
    }
    if (set_movs.length === 1){
        // рисую перемещения
        draw_movs(tp_info, set_movs[0], div_body)
        save_movs(tp_id)
    }
    else{
        // Выводим варианты перемещений
        let header = document.createElement('h5')
        header.innerText = 'Выберите один из сценариев перемещений внутри техпроцесса'
        header.id = 'h_set_movs_' + tp_id
        div_body.append(header)
        for (let i = 0; i < set_movs.length; i++){
            let set_mov = set_movs[i]
            let buton = document.createElement('button')
            buton.className = 'btn btn-outline-info p-1 m-2'
            buton.id = 'b_set_movs_' + i
            buton.setAttribute('onclick', 'draw_set_mov(' + i + ')')
            let mov_info = ''
            for (let j = 0; j < set_mov.length; j++){
                let parent_info = tp_info.stages.find(el => el.id === set_mov[j].parent_id)
                let offspring_info = tp_info.stages.find(el => el.id === set_mov[j].offspring_id)
                mov_info += 'Из ' + parent_info.name + ' в ' + offspring_info.name + ' ' + set_mov[j].delta + '<br>'
            }
            buton.innerHTML = mov_info
            div_body.append(buton)
        }
    }
}


function more_routs(this_button, tp_id, routs, rout_name, start_counter){
    let tp_info = new_tps_info.find(el => el.id === tp_id)
    let div_parent = this_button.parentElement
    let div_body = div_parent.parentElement
    div_parent.remove()
    draw_routs(div_body, tp_info, routs, rout_name, start_counter)
}


function draw_routs(div_body, tp_info, routs, rout_name, start_counter=0){
    let max_routs = (routs.length - start_counter <= 5) ? routs.length - start_counter : 5
    for (let i = 0; i < max_routs; i++){
        let div_rout = document.createElement('div')
        div_rout.className = 'btn btn-outline-link d-block p-0 text-left'
        div_body.appendChild(div_rout)
        let rout = routs[i + start_counter]
        let text_rout = ''
        for (let j = 0; j < rout.length; j++){
            text_rout += tp_info.stages.find(el => el.id === rout[j]).name
            if (j < rout.length - 1)
                text_rout += '&nbsp;&nbsp;>>&nbsp;&nbsp;'
        }
        let radio = document.createElement('input')
        radio.type = 'radio'
        radio.className = 'my-inline-blocks mx-1'
        radio.name = rout_name
        radio.id = rout_name + '_num_' + String(i + start_counter)
        div_rout.appendChild(radio)
        let my_label = document.createElement('label')
        my_label.innerHTML = text_rout
        my_label.setAttribute('for', radio.id)
        my_label.className = 'font-weight-normal'
        my_label.style['cursor'] = 'pointer'
        div_rout.appendChild(my_label)
    }
    let abs_max = max_routs + start_counter
    if (abs_max < routs.length){
        let div_root = document.createElement('div')
        div_root.className = 'btn btn-outline-link d-block p-0 text-left'
        div_body.appendChild(div_root)
        let b_more = document.createElement('button')
        b_more.className = 'btn btn-outline-secondary'
        b_more.innerText = 'Еще маршруты'
        let str_routs = JSON.stringify(routs)
        b_more.setAttribute('onclick', 'more_routs(this, ' + tp_info.id + ', ' + str_routs + ', "'
            + rout_name + '", ' + abs_max + ')')
        div_root.appendChild(b_more)
    }
    // Ставим значение по умолчанию
    let radio_checked = $('input[name="' + rout_name + '"]')
    if (radio_checked.filter(':checked').length === 0)
        radio_checked[0].checked = true
}


function save_movs(tp_id){
    let dict_set_movs = {'tp_id': tp_id, 'list_movs': []}
    let tag_movs = $("input[name^='r_" + tp_id +  "_']").filter(':checked')
    for (let i = 0; i < tag_movs.length; i++){
        let dict_mov = {}
        let mov_data = tag_movs[i].id.match(/p_(\d+)_o_(\d+)_num_(\d+)/)
        dict_mov['parent_id'] = parseInt(mov_data[1])
        dict_mov['offspring_id'] = parseInt(mov_data[2])
        dict_mov['rout_num'] = parseInt(mov_data[3])
        dict_mov['quant'] = parseFloat($("#s_quant_" + tag_movs[i].name).text())
        dict_set_movs.list_movs.push(dict_mov)
    }
    send_form_with_param('save_tp', JSON.stringify(dict_set_movs))
}


function draw_set_mov(mov_num){
    let header = $("[id^='h_set_movs_']")[0]
    let tp_id = parseInt(header.id.slice(11))
    let my_tp = json_object.new_tps.find(el => el.id === tp_id)
    let this_mov = set_movs[mov_num]
    let tag_body = header.parentElement
    tag_body.innerHTML = ''
    let tp_info = new_tps_info.find(el => el.id === tp_id)
    draw_movs(tp_info, this_mov, tag_body)
}

function draw_movs(tp_info, array_movs, div_body){
    for (let i = 0; i < array_movs.length; i++){
        let label = document.createElement('label')
        label.className = 'text-bold'
        label.innerText = 'Перемещение №' + String(i + 1) + '. '
        div_body.append(label)
        let stage_parent = tp_info.stages.find(el => el.id === array_movs[i].parent_id)
        let stage_offspring = tp_info.stages.find(el => el.id === array_movs[i].offspring_id)
        let description = document.createElement('span')
        description.innerText = 'Из ' + stage_parent.name + ' в ' + stage_offspring.name + ' '
        div_body.append(description)
        let text_quant = document.createElement('span')
        let mov_name = 'r_' + tp_info.id + '_p_' + array_movs[i].parent_id + '_o_' + array_movs[i].offspring_id
        text_quant.id = 's_quant_' + mov_name
        text_quant.innerText = array_movs[i].delta
        description.appendChild(text_quant)
        description.appendChild(document.createTextNode(' ед.'))
        div_body.append(document.createElement('br'))
        div_body.append(document.createTextNode('Выберите маршрут'))
        div_body.append(document.createElement('br'))
        let routs = rrc(tp_info, array_movs[i].parent_id, array_movs[i].offspring_id, [])
        sort_bubble(routs)
        let div_routs = document.createElement('div')
        div_body.append(div_routs)
        draw_routs(div_routs, tp_info, routs, mov_name)
    }
}


// Устарела. Удалить после 01.06.2025
// function choice_parent(){
//     $('input[id^="i_st_"]').each(function(){
//         let my_id = parseInt($(this)[0].id.match(/i_st_(\d+)_delta/)[1])
//         let my_delta = ($(this).val()) ? parseFloat($(this).val()) : 0
//         update_stages_tp[my_id] = {}
//         let old_val = $('#i_stage_' + my_id).val()
//         old_val = (old_val) ? parseFloat(old_val) : 0
//         update_stages_tp[my_id].value = old_val + my_delta
//         update_stages_tp[my_id].delta = my_delta
//     })
//     tp_is_valid = true
//     tp_modal.modal('hide')
//     csot(update_stages_tp.current_stage.id, update_stages_tp.tech_pro_id)
// }


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

// Возвращает все перестановки массива
function permutations(arr) {
    if (arr.length > 1) {
        let beg = arr[0]
        let arr1 = permutations(arr.slice(1))
        let arr2 = [];
        let l =  arr1[0].length;
        for(let i=0; i < arr1.length; i++)
            for(let j=0; j <= l; j++)
                arr2.push(arr1[i].slice(0, j).concat(beg, arr1[i].slice(j)));
        return arr2
    }
    else return [arr]
}


const objects_equal = (o1, o2) => Object.keys(o1).length === Object.keys(o2).length && Object.keys(o1).every(p => o1[p] === o2[p])
function arrays_equal(arr1, arr2){
    if (arr1.length !== arr2.length)
        return false
    for (let i = 0; i < arr1.length; i++){
        if (!objects_equal(arr1[i], arr2[i]))
            return false
    }
    return true
}


// retreive right child
function rrc(tp_info, current_stage_id, finish_stage_id, parent_ids){
    let list_routs = []
    let current_stage_info = tp_info.stages.find(el => el.id === current_stage_id)
    let children = current_stage_info.value.children
    for (let i = 0; i < children.length; i++){
        if (parent_ids.includes(children[i]))
            continue
        if (children[i] === finish_stage_id){
            let rout = [current_stage_id, finish_stage_id]
            list_routs.push(rout)
        }
        else {
            let deep_parent_ids = parent_ids.slice()
            deep_parent_ids.push(current_stage_id)
            let children_routs = rrc(tp_info, children[i], finish_stage_id, deep_parent_ids)
            if (children_routs.length){
                for (let j = 0; j < children_routs.length; j++){
                    children_routs[j].splice(0, 0, current_stage_id)
                    list_routs.push(children_routs[j])
                }
            }
        }
    }
    return list_routs
}
function sort_bubble(arr){
    let max = arr.length - 1
    for (let i = 0; i < arr.length - 1; i++){
        for (let j = 0; j < max; j++){
            if (arr[j].length > arr[j + 1].length)
                [arr[j], arr[j + 1]] = [arr[j + 1], arr[j]]
        }
        max--
    }
}