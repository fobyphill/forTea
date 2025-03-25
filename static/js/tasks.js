timer_task = null

function change_file_label(this_input){
    let my_id = this_input.id.slice(7)
    let my_label = $('#s_file_' + my_id)
    if (this_input.value){
        my_label.text(this_input.value)
        $('#b_load_' + my_id)[0].className = 'btn btn-outline-primary'
    }
    else my_label.innerText = 'Выберите файл'
}


function get_link(this_input, header_id, header_value, loc){
    clearTimeout(timer_task)
    timer_task = setTimeout(() =>{
        let task_code = this_input.id.slice(4)
        let result = $('#s_link_' + task_code)[0]
        if (this_input.value){
            $.ajax({url:'query-link',
                method:'get',
                dataType:'json',
                data: {link_code: this_input.value, header_id: header_id, class_type: loc},
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
        else{
            let match = header_value.match(/(table|contract)\.(\d+)/)
            let url = (match[1] === 'contract') ? '/contract' : '/manage-object'
            url += '?class_id=' + match[2]
            result.innerHTML = '<a target="_blank" href="' + url + '">Перейти к объектам</a>'
        }
    }, 1000)
}


function recount_alias(this_select, header_id, loc){
    let val = this_select.value
    let is_contract = (loc === 'c')
    let result = $('#div_alias_' + this_select.id.slice(4))
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


function change_stage(stage_id){
    clearTimeout(timer_task)
    timer_task = setTimeout(() => {
        let stage_info = JSON.parse($('#s_info_' + stage_id).html())
        let stage = $('#i_stage_' + stage_id)
        let new_val = parseFloat(stage.val())
        let text_error
        if (Math.abs(new_val) > Math.abs(stage_info.delta)) {
            text_error = 'Нельзя '
            text_error += (stage_info.delta > 0) ? 'увеличивать' : 'уменьшать'
            text_error += ' значение дельты'
        }
        else if (Math.abs(stage_info.delta - new_val) > Math.abs(stage_info.delta)) {
            text_error = 'Некорректное значение дельты стадии. Укажите значение '
            text_error += (stage_info.delta > 0) ? 'больше' : 'меньше'
            text_error += ' нуля'
        }
        if (text_error) {
            $('#l_universal_modal').text('Ошибка')
            $('#span_header').text('Неправильное значение')
            $('#div_body_text').text(text_error)
            $('#b_modal_cancel').text('ok')
            $("#b_modal_ok")[0].className = 'tag-invis'
            $('#universal_modal').modal('show')
            stage.val(stage_info.delta)
        }
        else{
            let tag_partners = $('#i_partners_' + stage_id)
            let partners_keys = Object.keys(stage_info.partners)
            if (partners_keys.length > 1) {
                $('#l_universal_modal').text('Внимание')
                $('#span_header').text('Изменение стадии')
                let my_html = 'Вы меняете значение стадии, которая взаимодействует с несколькими стадиями. ' +
                    'Укажите, как должны измениться значения стадий-партнеров<br>' +
                    '<table class="table w-100"><tr class="row"><td class="col text-center text-bold">Стадия</td>' +
                    '<td class="col text-center text-bold">Дельта</td></tr>'
                let partners = {}
                if (tag_partners.val().length){
                    partners = JSON.parse(tag_partners.val())
                    let new_delta = new_val - Object.values(partners).reduce((a, b) => a + b, 0) * -1
                    let i = 0
                    for (let k in partners){
                        partners[k] = (i > 0) ? partners[k] : partners[k] - new_delta
                        i++
                    }
                }
                else{
                    for (let i = 0; i < partners_keys.length; i++){
                        let val = stage_info.partners[partners_keys[i]]
                        partners[partners_keys[i]] = (i === 0) ? val + stage_info.delta - new_val : val
                    }
                }
                for (let pk in partners){
                    let my_stage = stage_info.stages.find((obj) => obj.id === parseInt(pk))
                    my_html += '<tr class="row"><td class="col">' + my_stage.name + '</td><td class="col">' +
                        '<input type="number" class="form-control change-stage" value="' + partners[pk] +
                        '" id="ins_' + pk + '_pt_' + stage_id + '" oninput="cps(this)"></td></tr>'
                }
                $('#div_body_text').html(my_html)
                $('#b_modal_cancel').text('Отмена')
                let button_modal_ok = $("#b_modal_ok")
                button_modal_ok.attr('class', 'btn btn-danger')
                button_modal_ok.attr('onclick', 'sapava(' + stage_id + ')')
                $('#universal_modal').modal('show')
            }
            else {
                let my_key = Object.keys(stage_info.partners)
                let my_dict = {}
                let old_delta = stage_info.partners[my_key[0]]
                let new_delta = stage_info.delta - new_val
                my_dict[my_key[0]] = old_delta + new_delta
                tag_partners.val(JSON.stringify(my_dict))
            }
        }
    }, 1000)
}


// check_partner_stages = check_partner_stages
function cps(this_input){
    let stage_id = this_input.id.match(/ins_\d+_pt_(\d+)/)[1]
    let stage = $('#i_stage_' + stage_id)
    let sum = 0
    $('.change-stage').each(function (){
        sum += parseFloat(this.value)
    })
    $('#b_modal_ok').attr('disabled', sum !== stage.val() * -1)
}

// sapava = save-partners-vals
function sapava(stage_id){
    let new_vals_partners = {}
    $('.change-stage').each(function(){
        let partner_id = this.id.match(/ins_(\d+)/)[1]
        new_vals_partners[partner_id] = parseFloat(this.value)
    })
    $('#i_partners_' + stage_id).val(JSON.stringify(new_vals_partners))
}

