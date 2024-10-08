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
    let all_vars = $('input[id^="const_' + const_id + '"]')
    let list_params = []
    all_vars.each(function(){
        let dict_param = {}
        let re = new RegExp('const_' + const_id + '_user_data_(\\d+)')
        dict_param.id = this.id.match(re)[1]
        if (this.type === 'checkbox')
            dict_param.value = (this.checked) ? 'True' : 'False'
        else if (['text', 'date', 'datetime-local'].includes(this.type))
            dict_param.value = '\'' + this.value + '\''
        // else if (this.type === 'datetime-local')
        //     dict_param.value = 'datetime.strptime(\'' + this.value + '\', \'%Y-%m-%dT%H:%M\')'
        // else if (this.type === 'date')
        //     dict_param.value = 'datetime.strptime(\'' + this.value + '\', \'%Y-%m-%d\').date()'
        else
            dict_param.value = this.value
        list_params.push(dict_param)
    })
    $.ajax({url:'calc-user-formula',
            method:'get',
            dataType:'json',
            data: {list_params: JSON.stringify(list_params), code: code, const_id: const_id, is_contract: is_contract},
            success:function(data){
                $('#div_const_' + const_id + '_result').html(data)
            },
            error: function () {
                $('#div_const_' + const_id + '_result').html('')
            }
        })
}