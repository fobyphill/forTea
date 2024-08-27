var new_tps_info = []
var update_stages_tp = {}
var tps_valid_result = true
var tp_is_valid = true
var tp_modal = $('#tp_modal')


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
                    tp_alert_calc()
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


// проверка корректности данных модального окна
function tp_alert_calc(){
    let sum = 0
    $('input[id^="i_st_"]').each(function(){
        sum += 1* $(this).val()
    })
    $('#b_tp_ok').attr('disabled', (sum !== update_stages_tp.control_val))
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

