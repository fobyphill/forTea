var typingTimer

// Подсказка "ссылка"
function promp_direct_link(this_input, location, class_id) {
    clearTimeout(typingTimer);
    typingTimer = setTimeout(() =>{
        let user_data = this_input.value
        let result = $('#' + this_input.getAttribute('list'))[0]
        $.ajax({url:'promp-direct-link',
            method:'get',
            dataType:'json',
            data: {location: location, class_id: class_id, user_data: user_data},
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
    }, 800)
}


function calc_user_data(const_id, code, is_contract=true){
    let csrf = $('input[name="csrfmiddlewaretoken"]').val()
    let all_vars = $('[id^="const_' + const_id + '"]')
    let list_params = []

    all_vars.each(function(){
        let dict_param = {}
        let re = new RegExp('const_' + const_id + '_user_data_(\\d+)')
        dict_param.id = this.id.match(re)[1]
        if (this.nodeName === 'TABLE'){
            let list_of_table = []
            let row_num = 0
            // Идем по строкам
            while(true){
                if (!$('input[id^="table_' + dict_param.id + '_num_' + row_num + '"]').length)
                    break
                // идет по столбцам
                let col_num = 0
                let row = []
                while (true){
                    let my_input = $("#table_" + dict_param.id + '_num_' + row_num + '_' + col_num)
                    if (my_input.length){
                        if (my_input[0].type === 'checkbox')
                            row.push(my_input.prop('checked'))
                        else if (my_input[0].type === 'number')
                            row.push(parseFloat(my_input.val()))
                        else row.push(my_input.val())
                        col_num++
                    }
                    else break
                }
                list_of_table.push(row)
                row_num++
            }
            dict_param.value = list_of_table
        }
        else if (this.type === 'checkbox')
            dict_param.value = (this.checked) ? 'True' : 'False'
        else
            dict_param.value = this.value
        list_params.push(dict_param)
    })
    let div_const_result = $('#div_const_' + const_id + '_result')
    div_const_result.text('Ожидайте, вычисляем')
    $.ajax({url:'calc-user-formula',
            method:'post',
            dataType:'json',
            data: {list_params: JSON.stringify(list_params), code: code, const_id: const_id, is_contract: is_contract,
            csrfmiddlewaretoken: csrf},
            success:function(data){
                div_const_result.html(data)
                let query_text = '[id^="const_' + const_id + '"]'
                $(query_text).each(function(){
                    if (this.getAttribute('defaultValue') === 'clean'){
                        this.value = ''
                        if (this.type === 'checkbox' && this.checked)
                            this.checked = false
                    }
                    else if (this.tagName === 'TABLE'){
                        let user_data_id = this.id.match(/const_\d+_user_data_(\d+)/)[1]
                        $('input[id^="table_' + user_data_id +'_"]').toArray().forEach((el) => {
                            if (el.getAttribute('defaultValue') === 'clean'){
                                el.value = ''
                                if (el.type === 'checkbox' && el.checked)
                                    el.checked = false
                            }
                        })
                    }
                })
                if (typeof data === 'string' && data.slice(0, 6).toLowerCase() === 'ошибка')
                    div_const_result.attr('class', 'text-red')
                else div_const_result.attr('class', '')

            },
            error: function (error) {
                div_const_result.html(error.statusText)
            }
        })
}

// atud = add table user data
function atud(this_button){
    let first_input = this_button.parentElement.parentElement.previousSibling.children[0].children[0]
    let details = first_input.id.match(/table_(\d+)_num_(\d+)/)
    let table_id = details[1]
    let row_num = parseInt(details[2]) + 1
    let col_counter = 0
    let result_row = document.createElement('tr')
    result_row.className = 'row m-0'
    this_button.parentElement.parentElement.parentElement.insertBefore(result_row, this_button.parentElement.parentElement)
    while(true){
        let var_table = $("#table_" + table_id + '_num_' + details[2] + '_' + col_counter)
        if (var_table.length){
            let new_col = document.createElement('td')
            new_col.className = 'col'
            result_row.appendChild(new_col)
            let my_input = document.createElement('input')
            my_input.className = 'form-control'
            my_input.id = 'table_' + table_id + '_num_' + row_num + '_' + col_counter
            my_input.type = var_table[0].type
            if (var_table[0].getAttribute('defaultValue') === 'clean' )
                my_input.setAttribute('defaultValue', 'clean')
            new_col.appendChild(my_input)
            let data_list = $("#table_" + table_id + '_list_' + details[2] + '_' + col_counter)
            if (data_list.length){
                let new_dl = data_list[0].cloneNode(false)
                new_dl.id = 'table_' + table_id + '_list_' + row_num + '_' + col_counter
                new_col.appendChild(new_dl)
                my_input.setAttribute('list', new_dl.id)
                my_input.setAttribute('oninput', var_table[0].getAttribute('oninput'))
            }
            col_counter++
        }
        else break
    }
}